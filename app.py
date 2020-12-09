import os
import threading
import time
import logging
import random

from flask import Flask, jsonify, request, abort, g, session
from flask_httpauth import HTTPBasicAuth
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import ScalarListType, JSONType
from flask_socketio import SocketIO
from werkzeug.security import generate_password_hash, check_password_hash

import config
from microflack_common.auth import token_auth, token_optional_auth
from microflack_common.utils import timestamp, url_for
from microflack_common import requests
import base64

# game stuff:
from src.schafkopf import schafkopf

logging.basicConfig(level=logging.INFO, format='[%(funcName)10s()-%(lineno)s:] %(message)s')

app = Flask(__name__)
config_name = os.environ.get('FLASK_CONFIG', 'dev')
app.config.from_object(getattr(config, config_name.title() + 'Config'))

db         = SQLAlchemy(app)
migrate    = Migrate(app, db)
basic_auth = HTTPBasicAuth()

message_queue = 'redis://' + os.environ['REDIS'] if 'REDIS' in os.environ \
    else None
if message_queue:
    socketio = SocketIO(message_queue=message_queue)
else:
    socketio = None

class Game(db.Model):
    """The Game model. ScalarListType"""
    __tablename__ = 'game'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(32), nullable=False, default="") # = highest declaration
    game_name     = db.Column(db.String(32), nullable=False, default="schafkopf")
    names         = db.Column(ScalarListType(), default=[])
    styles        = db.Column(ScalarListType(), default=[])  # HUMAN, RL

    comments      = db.Column(ScalarListType(), default=[])
    declarations  = db.Column(ScalarListType(int), default=[0, 0, 0, 0]) # = [decl1, decl2, etc.]
    highest_decl  = db.Column(db.String(32), nullable=False, default="")
    table_cards   = db.Column(ScalarListType(), default=[])  # = [HA, GA, EA]
    start_cards   = db.Column(JSONType, default={})  # = [ [start_cards_player1], etc.]
    # use start cards and table cards to reconstruct what card each player currently has
    final_points  = db.Column(ScalarListType(int), default=[])
    final_money   = db.Column(ScalarListType(int), default=[])

    created_at    = db.Column(db.Integer, default=timestamp)
    updated_at    = db.Column(db.Integer, default=timestamp, onupdate=timestamp)
    #roomid        = db.Column(db.Integer, nullable=False, default=0)

    @staticmethod
    def create(data):
        """Create a new game."""
        game = Game()
        game.from_dict(data, partial_update=False)
        return game

    def from_dict(self, data, partial_update=True):
        """Import game data from a dictionary. Converts model to representation (for api)"""
        for field in ['game_name', 'names', 'styles']:
            try:
                setattr(self, field, data[field])
            except KeyError:
                if not partial_update:
                    abort(400)

    def to_dict(self):
        """Export game to a dictionary. links are build e.g. /api/game/{}"""
        return {
            'id':           self.id,
            'title':        self.title,
            'game_name':    self.game_name,
            'names':        self.names,
            'styles':       self.styles,
            'comments':     self.comments,
            'declarations': self.declarations,
            'highest_decl': self.highest_decl,
            'table_cards':  self.table_cards,
            'start_cards':  self.start_cards,
            'final_points': self.final_points,
            'final_money':  self.final_money,
            'updated_at':   self.updated_at,
            'created_at':   self.created_at,
            '_links': {
                'self': url_for('get_game', id=self.id),
                'games': '/api/game/{}'.format(self.id),
                'tokens': '/api/tokens'
            }
        }

def check_user_playing(player_list):
    games = Game.query.all()
    for g in games:
        for p in player_list:
            for play in g["names"]:
                if str(p) == play:
                    return True
    return False

def check_game_type_valid(type, nu_players):
    if type=="schafkopf" and nu_players==4:
        return True
    return False

def get_game_options(game_name, names, styles):
    res = {}
    if game_name == "schafkopf":
        res["names"]          = names
        res["type"]           = styles
        res["nu_cards"]       = 8
        res["seed"]           = None
        res["active_player"]  = 3 # after reset player 0 starts!
        res["colors"]         =['E', 'G', 'H', 'S']
        res["value_conversion"] = {1: "7", 2: "8", 3: "9", 4: "U", 5: "O", 6: "K", 7: "X", 8: "A"}
    return res

def l2s(inlist):
    # converst list to strings
    return [str(i) for i in inlist]


@db.event.listens_for(Game, 'after_insert')
@db.event.listens_for(Game, 'after_update')
def after_game_update(mapper, connection, target):
    logging.warning("huhu")
    # if socketio is not None:
    #     socketio.emit('updated_model', {'class': target.__class__.__name__,
    #                                     'model': target.to_dict()})


@app.before_first_request
def before_first_request():
    """Start a background thread that looks for users that leave."""
    logging.warning("huhu")
    # def find_offline_users():
    #     with app.app_context():
    #         while True:
    #             User.find_offline_users()
    #             db.session.remove()
    #             time.sleep(5)
    #
    # if not app.config['TESTING']:
    #     thread = threading.Thread(target=find_offline_users)
    #     thread.start()

@app.route('/api/game', methods=['POST'])
def new_game():
    """
    Register a new game.
    This endpoint is publicly available.
    Create game only if none of the names is already playing elsewhere
    """
    logging.info(request.get_json())
    in_r = request.get_json()
    if not ("game_name" in in_r and "names" in in_r and "styles" in in_r):
        logging.error("Your request needs the fields type(<String>) and names(<[<String>,...])")
        abort(400)
    if check_user_playing(in_r["names"]):
        logging.error("One of the users is already playing....")
        abort(400)
    if not check_game_type_valid(in_r["game_name"], len(in_r["names"])):
        logging.error("I do not know your game... wrong type?, wrong nu names?")
        abort(400)
    # TODO     Test if the players are online!

    # shuffle users here (for random seats)
    random.shuffle(in_r["names"])
    # todo types also shuffled in same way!
    options = get_game_options(in_r["game_name"], in_r["names"], in_r["styles"])

    # create game
    db_game             = Game.create(in_r or {})
    db_game.start_cards = {}
    game_obj            = schafkopf(options)
    game_obj.reset()

    #sort hand cards:
    for i in range(game_obj.nu_players):
        db_game.start_cards[game_obj.player_names[i]] = l2s(game_obj.players[i].hand)

    db.session.add(db_game)
    db.session.commit()
    r = jsonify(db_game.to_dict())
    print(r)#558 bytes
    # TODO not all has to be send back!!!
    r.status_code = 201
    r.headers['Location'] = url_for('get_game', id=db_game.id)
    return r


@app.route('/api/game/<int:id>', methods=['GET'])
def get_game(id):
    """
    Return a Game.
    """
    return jsonify(Game.query.get_or_404(id).to_dict())

@app.route('/api/game_options/<int:id>/<string:name>', methods=['GET'])
def get_options(id, name):
    """
    Return the possible options for a game id and a name
    """
    game_db = Game.query.get_or_404(id)
    # create the game:
    res = get_game_options(game_db.game_name, game_db.names, game_db.styles)
    game_obj   = schafkopf(res)
    game_obj.reset()
    phase, error_msg = game_obj.playGame(game_db.declarations, game_db.table_cards, game_db.start_cards)
    r_dict = {}
    r_dict["phase"]     = phase
    r_dict["error_msg"] = error_msg

    if phase == "declaration":
        uu                = game_obj.getPossDeclarations(game_obj.players[game_obj.getIdFromName(name)].hand)
        r_dict["options"] = [game_obj.convertDecl2Index(i) for i in uu]
        r = jsonify(r_dict)
        r.status_code = 201
    elif phase == "playing":
        r.status_code = 201
    else: # in case of error
        r.status_code = 400
    return r

@app.route('/api/play/<int:id>', methods=['PUT'])
def send_declaration(id):
    """
    Send a declaration
    """
    # TODO
    # if game.id != g.jwt_claims['user_id']:
    #     abort(403)
    game_db = Game.query.get_or_404(id)
    in_r = request.get_json()
    player_idx = game_db.names.index(in_r["name"])
    action     = in_r["action"]
    # TODO check that name style is human! ??

    # create the game:
    res = get_game_options(game_db.game_name, game_db.names, game_db.styles)
    game_obj   = schafkopf(res)
    game_obj.reset()
    phase, error_msg = game_obj.playGame(game_db.declarations, game_db.table_cards, game_db.start_cards)
    r_dict = {}
    r_dict["phase"]     = phase
    r_dict["error_msg"] = error_msg

    if phase == "declaration":
        uu          = game_obj.getPossDeclarations(game_obj.players[player_idx].hand)
        poss_idx    = [game_obj.convertDecl2Index(i) for i in uu]
        if action in poss_idx:
            game_db.declarations[player_idx] = int(in_r["action"])
            print("commit - ", game_db.declarations)
            db.session.commit()
            r = jsonify(r_dict)
            r.status_code = 201
        else:
            r_dict["error_msg"] = "This declaration is not possible!!!"
            r = jsonify(r_dict)
            r.status_code = 400
    return r


if __name__ == '__main__':
    app.run()
