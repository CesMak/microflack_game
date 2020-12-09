#!/usr/bin/env python
import os
os.environ['FLASK_CONFIG'] = 'test'

import mock
import time
import unittest

from microflack_common.auth import generate_token
from microflack_common.test import FlackTestCase

import app
app.socketio = mock.MagicMock()
from app import app, db, Game, socketio

#30.11.2020 works?: first tests created
class GameTests(FlackTestCase):
    def setUp(self):
        print("inside setUp the Test")
        self.ctx = app.app_context()
        self.ctx.push()
        db.drop_all()  # just in case
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.drop_all()
        self.ctx.pop()

    def test_game(self):
        # create game
        names = ["tim", "max", "jan", "ella"]
        r, s, h = self.post('/api/game', data={'game_name': 'schafkopf',
                                                'names': names,
                                                'styles': ["HUMAN", "HUMAN", "HUMAN", "HUMAN"]})
        # use socketio to send cards to all players....
        self.assertEqual(s, 201)
        first_player = r["names"][0]
        game_id      = int(r["id"])
        # is it my turn --> see first_player and your name

        # get possible declarations
        for n in names:
            print("get options for", n)
            r, s, h = self.get('/api/game_options/'+str(game_id)+"/"+n)
            if r["phase"] == "declaration":
                # post declaration
                r, s, h = self.put('/api/play/1', data={'name': n,
                                                        'action': r["options"][0]})

        print("get options for", first_player)
        r, s, h = self.get('/api/game_options/'+str(game_id)+"/"+first_player)
        print(r)
        # post sending cards!


if __name__ == '__main__':
    unittest.main(verbosity=2)
