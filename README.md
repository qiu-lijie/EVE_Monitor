# EVE_Monitor

This is a monitor for the popular MMORPG [EVE Online](https://www.eveonline.com/). Currently it has the capacity to monitor market orders, to help you find the best priced items around.

## Installation

Run the following to install dependencies.

```bash
pip install -r requirements.txt
```

This project also requires the use of [Pushover](https://pushover.net/) in order to send real-time push notification. You need to go to their website to signup for a free trial account and get your own user key and app token. Store them in a file named `keys.py` in like the following.

```python
APP_TOKEN = 'APP_TOKEN'
USER_KEY  = 'USER_KEY'
```

You also need a file named `targets.json`, to specify the items you want to look for on the market. You can make this file by following `targets_template.json`. Note you can edit this file during run time to add/remove items and adjust their price threshold.

## Usage

```bash
python tasks.py
```

Note that most individual functions in market_monitor.py can be invoked on the command line directly. 

## License

[Apache license 2.0](https://choosealicense.com/licenses/apache-2.0/)

You can also send send isk to my in game character 0x1343D00

;)
