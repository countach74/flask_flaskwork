# flask_flaskwork

Flask extension to send basic debug-helpful information to Chrome for Flask requests.

## Install

`pip install flask_flaskwork`

## Usage

```python
from flask import Flask
from flask_flaskwork import Flaskwork

app = Flask(__name__)
Flaskwork(app)
```

## View requests information

1. Install chrome extension [Flaskwork](https://chrome.google.com/webstore/detail/flaskwork/hhigcljgpoilbfcdfemloacfgehakacc)
2. Open developer tools.
3. Open Flaskwork tab.
