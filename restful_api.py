#!/usr/bin/python3
import os
import sys
import logging
import logging.config
import time
import traceback

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest
import json
import redis
from raven.contrib.flask import Sentry


from exchange import Exchange
from order_loader import SimulatorLoader, CoreLoader
from balance_handler import BalanceHandler
import constants
import utils


logger = utils.get_logger()

app = Flask(__name__)


@app.route('/', methods=['POST'])
def index():
    try:
        if 'Key' not in request.headers:
            raise AttributeError("Missing 'Key' Header")
        else:
            api_key = request.headers['Key'].lower()

        timestamp = request.args.get('timestamp')
        if timestamp:
            timestamp = int(timestamp)
        else:
            timestamp = int(time.time() * 1000)

        try:
            method = request.form['method']

            if method == 'getInfo':
                output = liqui_exchange.get_balance_api(api_key=api_key)
            elif method == 'Trade':
                output = liqui_exchange.trade()
            elif method == 'WithdrawCoin':
                output = liqui_exchange.withdraw()
            else:
                raise AttributeError('Invalid method requested')

            logger.debug('Output: {}'.format(output))

            return jsonify({
                'success': 1,
                'return': output
            })
        except KeyError:
            raise KeyError('Method is missing in your request')
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': 0,
            'error': str(e)
        })


@app.route("/depth/<string:pairs>", methods=['GET'])
def depth(pairs):
    timestamp = request.args.get('timestamp')
    if timestamp:
        timestamp = int(timestamp)
    else:
        timestamp = int(time.time() * 1000)

    try:
        depth = liqui_exchange.get_depth_api(pairs, timestamp)
        return json.dumps(depth)
    except ValueError as e:
        logger.info("Bad Request: {}".format(e))
        return BadRequest()


if __name__ == "__main__":
    mode = os.environ.get('KYBER_ENV', 'dev')
    logging.config.fileConfig('logging.conf')

    rdb = utils.get_redis_db()

    if mode == 'simulation':
        data_imported = rdb.get('IMPORTED_SIMULATION_DATA')
        if not data_imported:
            logger.info('Import simulation data ...')
            ob_file = 'data/full_ob.dat'
            # ob_file = 'data/sample_ob.dat'
            try:
                utils.copy_order_books_to_db(ob_file, rdb)
            except FileNotFoundError:
                sys.exit('Data is missing.')
            rdb.set('IMPORTED_SIMULATION_DATA', 1)
            logger.info('Finish setup process.')

        order_loader = SimulatorLoader(rdb)
    else:
        order_loader = CoreLoader()

    balance_handler = BalanceHandler(rdb)
    liqui_exchange = Exchange(
        "liqui",
        [constants.KNC, constants.ETH, constants.OMG],
        rdb,
        order_loader,
        balance_handler,
        constants.LIQUI_ADDRESS,
        constants.BANK_ADDRESS,
        5 * 60
    )

    if mode != 'dev':
        sentry = Sentry(app, dsn='https://c2c05c37737d4c0a9e75fc4693005c2c:'
                        '17e24d6686d34465b8a97801e6e31ba4@sentry.io/241770')

    app.run(host='0.0.0.0', port=5000, debug=True)
