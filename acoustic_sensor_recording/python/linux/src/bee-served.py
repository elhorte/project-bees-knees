#!/usr/bin/env python3

# app.py
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, Bees!, What's the latest buzz?"
