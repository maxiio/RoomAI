#!/bin/python
import roomai.common
import roomai.bridge
import random


class BridgeEnv(roomai.common.AbstractEnv):
    '''
    The Bridge game environment
    '''


    def init(self, params = dict()):

        if "start_turn" in params:
            self.__params__["start_turn"] = params["start_turn"]
        else:
            self.__params__["start_turn"] = int(random.random() * 4)

        if "allcards" in params:
            self.__params__["allcards"] = params["allcards"]
        else:
            self.__params__["allcards"] = list(roomai.bridge.AllBridgePokerCards.values())
            random.shuffle(self.__params__["allcards"])

        self.public_state                       = roomai.bridge.BridgePublicState()
        self.public_state.__stage__             = 0
        self.public_state.__turn__              = self.__params__["start_turn"]

        self.person_states = [roomai.bridge.BridgePersonState() for i in range(4)]
        num = int(len(roomai.bridge.AllBridgePokerCards) / 4)
        for i in range(4):
            self.person_states[i].__hand_cards_dict__ = dict()
            for card in self.__params__["allcards"][i*num:(i+1)*num]:
                self.person_states[i].__hand_cards_dict__[card.key] = card
        self.person_states[self.public_state.turn].__available_actions__ \
            = self.available_actions(self.public_state, self.person_states[self.public_state.turn])


        self.private_state = roomai.bridge.BridgePrivateState()

        self.__gen_history__()
        return self.__gen_infos__(), self.public_state, self.person_states, self.private_state

    def forward(self, action):
        '''
        The Bridge game go forward with this action
        
        :param action: 
        :return: 
        '''

        pu  = self.public_state
        pes = self.person_states
        pr  = self.private_state
        if self.is_action_valid(action, pu, pes[pu.turn]):
            raise ValueError("%s is invalid action"%(action.key))
        pes[pu.turn].__available_actions__ = dict()

        if pu.stage == 0: ## the bidding stage
            pu.__bidding_action_history__.append(action)
            if len(pu.bidding_action_history) == 4:
                flag = True
                for i in range(4):
                    flag = flag and (pu.bidding_action_history[i].bidding_option == "pass")
                if flag == True:
                    pu.__is_terminal__ = True
                    pu.__scores__      = [0,0,0,0]
                    self.__gen_history__()
                    return self.__gen_infos__(), self.public_state, self.person_states, self.private_state

            if len(pu.bidding_action_history) > 3:
                flag = True
                for i in range(1,4):
                    flag = flag and (pu.bidding_action_history[-i].bidding_option == "pass")
                if flag == True:
                    self.__bidding_to_playing__()

            if action.bidding_option == "bid":
                pu.__bidding_candidate_contract_point__ = action.bidding_point
                pu.__bidding_candidate_contract_suit__  = action.bidding_suit
                pu.__bidding_last_bidder__ = pu.turn

            pu.__previous_id__     = pu.turn
            pu.__previous_action__ = action
            pu.__turn__            = (pu.turn + 1) % 4



        elif pu.stage == 1: ## the playing stage
            pu.cards_on_table.append(action.card)
            self.__remove_card_from_hand_cards__(pes[pu.real_turn], action.card)

            if len(pu.cards_on_table) == 4:
                playerid1,playerid2 = self.__compute_winner__()
                pu.__playing_win_tricks_sofar__[playerid1] += 1
                pu.__playing_win_tricks_sofar__[playerid2] += 1
                if len(pes[pu.real_turn].hand_cards) == 0:
                    pu.__is_terminal__ = True
                    if pu.win_count_sofar[pu.dealerid] > pu.win_count_sofar[(pu.dealerid + 1)%4] + pu.trump.point_rank:
                        pu.__scores__ = [-1,-1,-1,-1]
                        pu.__scores__[pu.dealerid] = 1
                        pu.__scores__[(pu.dealerid+2)%4] = 1
                    else:
                        pu.__scores__ = [1,1,1,1]
                        pu.__scores__[pu.dealerid] = -1
                        pu.__scores__[(pu.dealerid+2)%4] = -1
            else:
                pu.__playing_real_turn__ = (pu.__playing_real_turn__ + 1) % 4
                pu.__turn__      = (pu.__turn__ + 1)%4


        else:
            raise ValueError("The public_state.stage = %d is invalid"%(self.public_state.stage))


        self.__gen_history__()
        return self.__gen_infos__(), self.public_state,self.person_states, self.private_state

    def __remove_card_from_hand_cards__(self, person_state, card):
        del person_state.__hand_cards_dict__[card.key]

    def __compare_card_with_trump__(self, card1, card2, trump):
        if card1.suit == trump.suit and card2.suit == trump.suit:
            return roomai.bridge.BridgeBidPokerCard.compare(card1, card2)
        elif card1.suit == trump.suit and card2.suit != trump.suit:
            return 1
        elif card1.suit != trump.suit and card2.suit == trump.suit:
            return -1
        else:
            return roomai.bridge.BridgeBidPokerCard.compare(card1, card2)

    def __compute_winner__(self, pu):
        max_id   = 0
        max_card = pu.cards_on_table[0]
        for i in range(1,4):
            if self.__compare_card_with_trump__(max_card, pu.cards_on_table[i], pu.trump):
                max_id   = i
                max_card = pu.cards_on_table[i]

        return max_id, (max_id + 2)%2

    def __bidding_to_playing__(self):
        pass

    def __available_contract__(self, pu, point, suit):
        if point not in roomai.bridge.contract_point_to_rank:
            raise  ValueError("The contract point must be one of (%s)"%(",".join(list(roomai.bridge.contract_point_to_rank.keys()))))
        if suit not in  roomai.bridge.contract_suit_to_rank:
            raise  ValueError("The contract suit must be one of (%s)"%(",".join(list(roomai.bridge.contract_suit_to_rank.keys()))))
        suit_rank  = roomai.bridge.contract_suit_to_rank[suit]
        point_rank = roomai.bridge.contract_point_to_rank[point]

        if point_rank > roomai.bridge.contract_point_to_rank[pu.bidding_candidate_contract_point]:
            return True
        elif point_rank == roomai.bridge.contract_point_to_rank[pu.bidding_candidate_contract_point]:
            if suit_rank > roomai.bridge.suit_to_suit_rank[pu.bidding_candidate_contract_suit]:
                return True
            else:
                return False
        else:
            return False

    @classmethod
    def is_action_valid(cls, action, public_state, person_state):
        return action.key in person_state.available_actions

    @classmethod
    def available_actions(self, public_state, person_state):
        if public_state.stage == "bidding": ## the bidding stage
            available_actions = dict()
            for point in roomai.bridge.contract_point_to_rank:
                for suit in roomai.bridge.contract_suit_to_rank:
                    if BridgeEnv.__available_contract__(point, suit) == True:
                        key = "bidding_bid_%s_%s"%(point, suit)
                        available_actions[key] = roomai.bridge.BridgeAction.lookup(key)
            available_actions["bidding_pass"] = roomai.bridge.BridgeAction.lookup("bidding_pass")

            if len(public_state.__bidding_action_history__) >= 1:
                pre_action  = public_state.__bidding_action_history__[-1]
                if pre_action.bidding_option == "bid":
                    key = "bidding_double"
                    available_actions[key] = roomai.bridge.BridgeAction.lookup(key)

                if pre_action.bidding_option == "double":
                    key = "redouble"
                    available_actions[key] = roomai.bridge.BridgeAction.lookup(key)

            if len(public_state.__bidding_action_history__) >= 3:
                pre_action1 = public_state.__bidding_action_history__[-1]
                pre_action2 = public_state.__bidding_action_history__[-2]
                pre_action3 = public_state.__bidding_action_history__[-3]
                if pre_action3.bidding_option == "bid" and pre_action2.bidding_option == "pass" and pre_action1.bidding_option == "pass":
                    key = "double"
                    available_actions[key] = roomai.bridge.BridgeAction.lookup(key)

            return available_actions


        elif public_state.stage == 1: ## the playing stage
            available_actions = dict()
            if public_state.cards_on_table == []:
                for card in person_state.hand_cards:
                    key = "playing_%s"%(card.key)
                    available_actions[key] = roomai.bridge.BridgeAction.lookup(key)
            else:
                for card in person_state.hand_cards:
                    if card.suit == public_state.cards_on_table[0].suit:
                        key = "playing_%s" % (card.key)
                        available_actions[key] = roomai.bridge.BridgeAction.lookup(key)
                if len(available_actions) == 0:
                    for card in person_state.hand_cards:
                        key = "playing_%s" % (card.key)
                        available_actions[key] = roomai.bridge.BridgeAction.lookup(key)

            return available_actions

        else:
            raise ValueError("The public_state.stage = %d is invalid. The public_state.stage = 0 means the bidding stage, The public_state.stage = 1 means the playing stage"%(self.public_state.stage))

