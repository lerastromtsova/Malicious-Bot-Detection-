import os

import pymongo
from bson.json_util import dumps
from bson.json_util import loads
from dotenv import dotenv_values
from flask import Flask, render_template, request
from flask import session, redirect
from flask_babel import Babel

from database_adapter import get_user_by_id, get_users_by_name
from database_adapter import get_comments_by_user
from models import bot_check_results

import iuliia

app = Flask(__name__)
babel = Babel(app)

config = dotenv_values(".env")
if not config:
    config = os.environ

if config['LOCAL_DB'] != '0':
    db_client = pymongo.MongoClient(host="localhost", port=27017)
else:
    conn_uri = f'mongodb+srv://' \
               f'{config["MONGO_DB_USERNAME"]}:' \
               f'{config["MONGO_DB_PASSWORD"]}' \
               f'@{config["MONGO_DB_HOST"]}' \
               f'?tls=true&authSource=admin&' \
               f'replicaSet={config["MONGO_REPLICA_SET"]}&tlsInsecure=true'
    db_client = pymongo.MongoClient(conn_uri)

USERS_LIMIT = 10
USERS_TO_LABEL_LIMIT = 10

URL_SHARING_USERS_TO_LABEL = [
    702784146, 694974368, 708042007, 649499218, 707754356, 687545774,
    708269978, 708899664, 228873813, 189830086, 2682374, 26779373,
    210672246, 3938809, 573785432, 713634297, 627826591, 170652421,
    714581383, 719005425
]
HASHTAG_SEQUENCES_USERS_TO_LABEL = [
    19514526, 656445370, 13014907, 415217672, 45685036,
    633339603, 75932, 651242477, 345899328, 681273748,
    175874956, 470385550, 692756807, 223692672, 222939753,
    137702183, 423737165, 224720979, 619650776, 628540177
]
USER_IDS_TO_LABEL = URL_SHARING_USERS_TO_LABEL \
                    + HASHTAG_SEQUENCES_USERS_TO_LABEL


@app.route("/")
def index():
    return redirect('search')


@app.route("/search")
def search():
    if request.args:
        query = request.args.get('user')
        if query.isdigit():
            users = get_user_by_id(db_client, query)
        else:
            query = iuliia.translate(query, schema=iuliia.WIKIPEDIA)
            users = get_users_by_name(
                db_client,
                query,
                users_limit=USERS_LIMIT
            )
        if users:
            # comments = get_comments_by_user(db_client, user_id)
            return render_template('index.html', users=users, comments=[])
        return render_template('index.html', error='Not Found')
    return render_template('index.html')


@app.route("/is_bot")
def is_bot():
    if request.args:
        user_id = int(request.args.get('user'))
        users = get_user_by_id(db_client, user_id)
        bot_check_result = bot_check_results(users[0])
        comments = get_comments_by_user(db_client, user_id)
        return render_template(
            'bot-check-results.html',
            user=users[0],
            is_bot=bot_check_result,
            comments=comments
        )
    return render_template('index.html')


@app.route("/contact")
def contact():
    return render_template('contact.html')


@app.route("/methods")
def methods():
    return render_template('methods.html')


@app.route('/language=<language>')
def set_language(language=None):
    session['language'] = language
    return redirect(request.referrer)


@babel.localeselector
def get_locale():
    if request.args.get('language'):
        session['language'] = request.args.get('language')
    return session.get('language', 'en')


app.config['LANGUAGES'] = {
    'en': '🇬🇧 English',
    'ru': '🇷🇺 Русский',
    'uk': '🇺🇦 Українська'
}

app.secret_key = config['WEB_SECRET']


@app.context_processor
def inject_conf_var():
    return dict(AVAILABLE_LANGUAGES=app.config['LANGUAGES'],
                CURRENT_LANGUAGE=session.get(
                    'language',
                    request.accept_languages.best_match(
                        app.config['LANGUAGES'].keys()
                    )
                ))


@app.route("/labelling")
def labelling():
    if request.args.get('prolific_id') and 'users_to_label' not in session:
        session['prolific_id'] = request.args.get('prolific_id')
        aggregation = db_client.dataVKnodup.users.aggregate([
            {'$match': {"$and": [
                {
                    "labels": {"$not": {
                        "$elemMatch": {"by": session['prolific_id']}
                    }}
                },
                {
                    "vk_id": {
                        "$in": USER_IDS_TO_LABEL
                    }
                }
            ]}},
            {'$project': {
                'vk_id': 1,
                'photo_100': 1,
                'screen_name': 1,
                'first_name': 1,
                'last_name': 1,
                'deactivated': 1,
                'labels_count': {'$size': {"$ifNull": ["$labels", []]}},
                'more_than_three_labels': {'$gt': [
                    {'$size': {"$ifNull": ["$labels", []]}}, 3
                ]}
            }},
            {'$match': {'more_than_three_labels': False}},
            {'$sample': {'size': USERS_TO_LABEL_LIMIT}},
            {'$sort': {'labels_count': 1}}
        ])
        users_to_label = dumps(list(aggregation), separators=(',', ':'))
        session['users_to_label'] = users_to_label
        session['total_to_label'] = USERS_TO_LABEL_LIMIT + 1
    if 'prolific_id' in session and 'users_to_label' in session:
        prolific_id = session['prolific_id']
        users_to_label = loads(session['users_to_label'])
        prev_user_id = int(request.args.get('prev_user_id'))
        if request.args.get('prev_user_result'):
            prev_user_result = request.args.get('prev_user_result')
            db_client.dataVKnodup.users.update_one(
                {'vk_id': int(users_to_label[prev_user_id]['vk_id'])},
                {'$push': {'labels': {
                    'by': prolific_id,
                    'result': prev_user_result
                }}}
            )
        session['total_to_label'] = USERS_TO_LABEL_LIMIT - prev_user_id - 1
        if session['total_to_label'] == 0:
            #     no more users to label
            return redirect('labelling-end')
        next_user_id = prev_user_id + 1
        user = users_to_label[next_user_id]
        comments = get_comments_by_user(db_client, user['vk_id'])
        return render_template(
            'labelling.html',
            prolific_id=prolific_id,
            current_user=user,
            comments=comments,
            count=next_user_id
        )
    return render_template('labelling.html')


@app.route("/labelling-end")
def labelling_end():
    if request.args.get('explain_decisions'):
        if 'prolific_id' in session:
            db_client.dataVKnodup.free_responses.insert_one({
                'prolific_id': session['prolific_id'],
                'free_text': request.args.get('explain_decisions')
            })
        session.pop('prolific_id', None)
        session.pop('users_to_label', None)
        return render_template(
            'labelling-end.html',
            completion_code=config['COMPLETION_CODE']
        )
    return render_template('labelling-end.html')


if __name__ == "__main__":
    app.run()
