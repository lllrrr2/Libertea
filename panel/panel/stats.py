import json
import psutil
import requests
from . import utils
from . import config
from pymongo import MongoClient
from datetime import datetime, timedelta

___json_cache = {}
___json_cache_last_cleanup = datetime.now()

def cleanup_json_cache(force=False):
    global ___json_cache
    global ___json_cache_last_cleanup

    if force:
        # clear all
        ___json_cache = {}
        return

    if (datetime.now() - ___json_cache_last_cleanup).total_seconds() < 30:
        return

    ___json_cache_last_cleanup = datetime.now()

    try:
        for key in list(___json_cache.keys()):
            if ___json_cache[key][0] < datetime.now():
                del ___json_cache[key]
    except Exception as e:
        print("Error cleaning up json cache:", e)

def populate_json_cache(file_name):
    global ___json_cache
    with open(config.get_root_dir() + file_name, 'r') as f:
        temp_data = json.loads(f.read())
        data = {}
        for user in temp_data['users']:
            key = list(user.keys())[0]
            domains = {}
            # remove domains with ~0 usage from [total] (ip scans)
            if key == '[total]':
                for domain in list(user[key]['domains'].keys()):
                    if user[key]['domains'][domain]['megabytes'] > 0.1:
                        domains[domain] = user[key]['domains'][domain]
            data[key] = {
                'megabytes': user[key]['megabytes'],
                'ips': user[key]['ips'],
                'domains': domains
            }
    ___json_cache[file_name] = (datetime.now() + timedelta(seconds=60), data)


def ___get_total_gigabytes(date, date_resolution, conn_url, domain=None, db=None):
    global ___json_cache
    try:
        # cache if not for today
        cache_result = False
        if date_resolution == 'day':
            file_name = f'./data/usages/{date_resolution}/{date.strftime("%Y-%m-%d")}.json'
            cache_result = date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_resolution == 'month':
            file_name = f'./data/usages/{date_resolution}/{date.strftime("%Y-%m")}.json'
            cache_result = date < datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else: 
            raise Exception('Invalid date resolution ' + str(date_resolution))

        cache_entry_name = ''
        if cache_result:
            if db is None:
                client = config.get_mongo_client()
                db = client[config.MONGODB_DB_NAME]
            
            if date_resolution == 'day':
                cache_entry_name = date.strftime("%Y-%m-%d") + '-trafficGbV2-' + conn_url
            elif date_resolution == 'month':
                cache_entry_name = date.strftime("%Y-%m") + '-trafficGbV2-' + conn_url

            if domain is not None:
                cache_entry_name += '-' + domain
            
            # check if already cached
            stats_cache = db.stats_cache
            cached = stats_cache.find_one({'_id': cache_entry_name})
            if cached is not None:
                gigabytes = cached['gigabytes']
                return gigabytes

        if file_name not in ___json_cache or ___json_cache[file_name][0] < datetime.now():
            populate_json_cache(file_name)
        data = ___json_cache[file_name][1]
        cleanup_json_cache()

        gigabytes = 0
        if conn_url in data:
            entry = data[conn_url]
            if domain is None:
                gigabytes = entry['megabytes'] / 1024
            else:
                if domain in entry['domains']:
                    gigabytes = entry['domains'][domain]['megabytes'] / 1024
                else:
                    gigabytes = 0

        if cache_result:
            stats_cache = db.stats_cache
            stats_cache.update_one(
                {'_id': cache_entry_name},
                {'$set': {
                    'gigabytes': gigabytes,
                }},
                upsert=True
            )

        return gigabytes
                
    except Exception as e:
        print("Error getting total gigabytes:", e)
        return None

def ___get_total_ips(date, date_resolution, conn_url, db=None):
    global ___json_cache
    try:
        # cache if not for today
        cache_result = False
        if date_resolution == 'day':
            file_name = f'./data/usages/{date_resolution}/{date.strftime("%Y-%m-%d")}.json'
            cache_result = date < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_resolution == 'month':
            file_name = f'./data/usages/{date_resolution}/{date.strftime("%Y-%m")}.json'
            cache_result = date < datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else: 
            raise Exception('Invalid date resolution ' + str(date_resolution))

        cache_entry_name = ''
        if cache_result:
            if db is None:
                client = config.get_mongo_client()
                db = client[config.MONGODB_DB_NAME]
            
            if date_resolution == 'day':
                cache_entry_name = date.strftime("%Y-%m-%d") + '-ips-' + conn_url
            elif date_resolution == 'month':
                cache_entry_name = date.strftime("%Y-%m") + '-ips-' + conn_url
            
            # check if already cached
            stats_cache = db.stats_cache
            cached = stats_cache.find_one({'_id': cache_entry_name})
            if cached is not None:
                return cached['ips']
            
        if file_name not in ___json_cache or ___json_cache[file_name][0] < datetime.now():
            populate_json_cache(file_name)
        data = ___json_cache[file_name][1]
        cleanup_json_cache()

        connections = 0
        if conn_url in data:
            entry = data[conn_url]
            connections = entry['ips']
        
        if cache_result:
            stats_cache = db.stats_cache
            stats_cache.update_one(
                {'_id': cache_entry_name},
                {'$set': {
                    'ips': connections,
                }},
                upsert=True
            )
        connections = str(connections)
        return connections
    except:
        return '-'

def get_gigabytes_today(user_id, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']
    return ___get_total_gigabytes(datetime.now(), 'day', conn_url, db=db)

def get_gigabytes_this_month(user_id, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']
    return ___get_total_gigabytes(datetime.now(), 'month', conn_url, db=db)

def get_ips_today(user_id, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']
    return ___get_total_ips(datetime.now(), 'day', conn_url, db=db)

def get_ips_this_month(user_id, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']
    return ___get_total_ips(datetime.now(), 'month', conn_url, db=db)

def get_gigabytes_today_all():
    return ___get_total_gigabytes(datetime.now(), 'day', '[total]')

def get_traffic_per_day(user_id, days=7, domain=None, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']

    xs = []
    ys = []
    for i in range(days - 1, -1, -1):
        date_obj = datetime.now() - timedelta(days=i)
        date = date_obj.strftime('%Y-%m-%d')
        xs.append(date)
        try:
            traffic = ___get_total_gigabytes(date_obj, 'day', conn_url, domain=domain, db=db)
            if traffic is None:
                traffic = 0

            if domain is not None:
                extra_traffic = utils.online_route_get_traffic(domain, date_obj.year, date_obj.month, date_obj.day, db=db)
                if extra_traffic is not None:
                    for port in extra_traffic:
                        traffic += (extra_traffic[port]['received_bytes'] + extra_traffic[port]['sent_bytes']) / 1024 / 1024 / 1024

            ys.append(traffic)
        except:
            ys.append(None)

    return xs, ys

def get_traffic_per_day_all(days=7, domain=None, include_extra_data_for_online_route=False):
    xs = []
    ys = []

    client = config.get_mongo_client()
    db = client[config.MONGODB_DB_NAME]

    for i in range(days - 1, -1, -1):
        date_obj = datetime.now() - timedelta(days=i)
        date = date_obj.strftime('%Y-%m-%d')
        xs.append(date)
        try:
            traffic = ___get_total_gigabytes(date_obj, 'day', '[total]', domain=domain, db=db)
            if traffic is None:
                traffic = 0

            if domain is not None:
                extra_traffic = utils.online_route_get_traffic(domain, date_obj.year, date_obj.month, date_obj.day, db=db)
                if extra_traffic is not None:
                    for port in extra_traffic:
                        traffic += (extra_traffic[port]['received_bytes'] + extra_traffic[port]['sent_bytes']) / 1024 / 1024 / 1024
            ys.append(traffic)
        except:
            ys.append(None)

    return xs, ys

def get_gigabytes_past_30_days(user_id, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']

    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    sum_gigabytes = 0
    while start_date <= end_date:
        cur_gigabytes = ___get_total_gigabytes(start_date, 'day', conn_url, db=db)
        if cur_gigabytes is not None:
            sum_gigabytes += cur_gigabytes
        start_date += timedelta(days=1)

    return sum_gigabytes

def get_gigabytes_past_30_days_all(db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]

    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()
    sum_gigabytes = 0
    while start_date <= end_date:
        cur_gigabytes = ___get_total_gigabytes(start_date, 'day', '[total]', db=db)
        if cur_gigabytes is not None:
            sum_gigabytes += cur_gigabytes
        start_date += timedelta(days=1)

    return sum_gigabytes


def get_gigabytes_this_month_all():
    return ___get_total_gigabytes(datetime.now(), 'month', '[total]')

def get_ips_today_all():
    return ___get_total_ips(datetime.now(), 'day', '[total]')

def get_ips_this_month_all():
    return ___get_total_ips(datetime.now(), 'month', '[total]')
    
def get_connected_ips_right_now(user_id, long=False, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    user = users.find_one({"_id": user_id})
    conn_url = user['connect_url']
    
    try:
        req = requests.get(f'https://localhost/{ conn_url }/connected-ips-count' + ('-long' if long else ''), verify=False, timeout=0.1)
        if req.status_code == 200:
            return req.text
    except:
        pass

    return None

def get_total_connected_ips_right_now(long=False):
    try:
        req = requests.get(f'https://localhost/{ config.get_admin_uuid() }/total-connected-ips-count' + ('-long' if long else ''), verify=False, timeout=0.1)
        if req.status_code == 200:
            return int(req.text)
    except:
        pass

    return None

def save_connected_ips_count(db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]
    users = db.users
    connected_ips_log = db.connected_ips_log

    cur_hour_min = datetime.now().strftime('%H:%M')
    total_connected_ips = 0
    total_connected_users = 0
    user_ids = list(users.find({}, {'_id': 1}))
    connected_user_ids = []
    for user_id in user_ids:
        user_id = user_id['_id']
        connected_ips = get_connected_ips_right_now(user_id, long=True, db=db)
        if connected_ips is not None:
            if connected_ips.isdigit():
                connected_ips = int(connected_ips)
                if connected_ips > 0:
                    total_connected_users += 1
                    connected_user_ids.append(user_id)
                entry_key = str(user_id) + '--' + str(datetime.now().year) + '-' + str(datetime.now().month) + '-' + str(datetime.now().day)
                connected_ips_log.update_one(
                    {'_id': entry_key},
                    {'$set': {
                        cur_hour_min: connected_ips,
                    }},
                    upsert=True
                )
                total_connected_ips += connected_ips
    entry_key = 'ALL--' + str(datetime.now().year) + '-' + str(datetime.now().month) + '-' + str(datetime.now().day)
    connected_ips_log.update_one(
        {'_id': entry_key},
        {
            '$setOnInsert': {
                'connected_users': [],
            }
        },
        upsert=True
    )

    connected_ips_log.update_one(
        {'_id': entry_key},
        {
            '$set': {
                cur_hour_min: total_connected_ips,
            },
            '$addToSet': {
                'connected_users': {
                    '$each': connected_user_ids
                }
            }
        },
        upsert=True
    )

    connected_ips_log.update_one(
        {'_id': "ALL--Recent"},
        {
            '$set': {
                "total_connected_ips": total_connected_ips,
                "total_connected_users": total_connected_users,
            }
        },
        upsert=True
    )
    

def get_connected_ips_over_time(user_id, year, month, day, db=None):
    if db is None:
        client = config.get_mongo_client()
        db = client[config.MONGODB_DB_NAME]

    connected_ips_log = db.connected_ips_log
    entry_key = str(user_id) + '--' + str(year) + '-' + str(month) + '-' + str(day)

    try:
        return dict(connected_ips_log.find_one({'_id': entry_key}))
    except Exception as e:
        return {}

def get_all_connected_ips_over_time(year, month, day, db=None):
    return get_connected_ips_over_time('ALL', year, month, day, db)

def get_connected_users_now(long=False):
    try:
        req = requests.get(f'https://localhost/{ config.get_admin_uuid() }/total-connected-users-count' + ('-long' if long else ''), verify=False, timeout=0.1)
        if req.status_code == 200:
            return int(req.text)
    except:
        pass

    return None

def get_connected_users_today(db=None):
    try:
        if db is None:
            client = config.get_mongo_client()
            db = client[config.MONGODB_DB_NAME]

        connected_ips_log = db.connected_ips_log
        entry_key = 'ALL--' + str(datetime.now().year) + '-' + str(datetime.now().month) + '-' + str(datetime.now().day)
        res = connected_ips_log.find_one({'_id': entry_key})
        return len(list(res['connected_users']))
    except Exception as e:
        return '-'


def get_system_stats_cpu():
    try:
        return str(int(psutil.cpu_percent())) + '%'
    except:
        pass
    return '-'

def get_system_stats_ram():
    try:
        return str(int(psutil.virtual_memory()[2])) + '%'
    except:
        pass
    
    return '-'
