import collections
import warnings
from threading import Thread

import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from traceback import print_exc
import pickle

import googlemaps
from flask import Flask, render_template, jsonify
import time

from os.path import exists

try:
    from private_settings import GOOGLE_KEY, LOCATION_FROM, LOCATION_TO
except ImportError:
    warnings.warn('Please create private_settings.py module. See README.md')
    raise

gmaps = googlemaps.Client(key=GOOGLE_KEY)

app = Flask(__name__, template_folder='.')

_CURRENT_JAM = 0
_UPDATE_TIME = datetime.now()
_LAST_HOUR = collections.deque(maxlen=240)


@app.route('/')
def index():
    return render_template('traffic_flask.jinja2')


@app.route('/get_latest_data')
def get_latest_data():
    return jsonify({'current_jam': _CURRENT_JAM, 'update_time': _UPDATE_TIME})


def google_checker():
    global _CURRENT_JAM, _UPDATE_TIME
    while True:
        origins = LOCATION_FROM
        destinations = LOCATION_TO
        now = datetime.now()
        if 22 <= now.hour or now.hour < 6:
            start_time = now.replace(hour=6, minute=0)
            if start_time < now:
                start_time += timedelta(days=1)
            print('Sleeping until 6:00')
            time.sleep((start_time - now).total_seconds())
            continue

        if 6 <= now.hour < 14:
            origins, destinations = destinations, origins

        try:
            result = gmaps.distance_matrix(origins=origins,
                                           destinations=destinations,
                                           departure_time=now, )
        except:
            print_exc()
            continue
        duration = result['rows'][0]['elements'][0].get('duration_in_traffic', {}).get('value')
        if not duration:
            continue
        duration = float(duration) / 60
        extra_time = duration - 30
        _CURRENT_JAM = extra_time
        _UPDATE_TIME = now
        _LAST_HOUR.append(_CURRENT_JAM)
        plt.clf()
        axes = plt.gca()
        axes.set_ylim([min(min(_LAST_HOUR) - 1, -5), max(_LAST_HOUR) + 1])
        plt.plot(_LAST_HOUR)
        plt.title('Jam history (around 2 hours)')
        plt.ylabel('Jam times')
        plt.savefig('static/jam.png')
        with open('pickled_times.pickle', 'wb+') as f:
            pickle.dump(_LAST_HOUR, f)
        # plt.show()
        print(_UPDATE_TIME, _CURRENT_JAM)
        time.sleep(30)


if __name__ == '__main__':
    if exists('pickled_times.pickle'):
        with open('pickled_times.pickle', 'rb') as f:
            try:
                _LAST_HOUR = pickle.load(f)
            except EOFError:
                pass
            else:
                _LAST_HOUR = collections.deque(_LAST_HOUR, maxlen=240)
                _CURRENT_JAM = _LAST_HOUR[-1]
    checker = Thread(target=google_checker)
    checker.daemon = True
    checker.start()
    app.run(host='0.0.0.0', port=8017)
