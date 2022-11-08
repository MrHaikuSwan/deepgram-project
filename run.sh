#!/bin/sh

export FLASK_APP=./src/index.py
export FLASK_ENV=development
export FLASK_DEBUG=1

flask run