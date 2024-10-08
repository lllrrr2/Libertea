import random
import requests
import traceback
import threading
from . import stats
from . import utils
from . import config
from . import certbot
from . import health_check
from . import settings
from . import sysops
from . import welcome
from . import admin
from . import user
from . import api
import uwsgidecorators
from flask import Flask
from datetime import datetime
from pymongo import MongoClient
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def log_cron(cron_uid, *args):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - CRON " + cron_uid + " - ", *args)

def periodic_update_domains():
    cron_uid = 'periodic_update_domains_' + str(random.randint(0, 1000000))
    log_cron(cron_uid, "Updating domains cache")
    domains = utils.get_domains()
    for domain in domains:
        utils.update_domain_cache(domain)
    log_cron(cron_uid, "DONE updating domains cache")

@uwsgidecorators.timer(2 * 60)
def periodic_update_domains_cron(signal):
    periodic_update_domains()

@uwsgidecorators.timer(5 * 60)
def periodic_update_users_stats(signal):
    cron_uid = 'periodic_update_users_stats_' + str(random.randint(0, 1000000))
    log_cron(cron_uid, "Updating users stats cache")
    stats.cleanup_json_cache(force=True)
    users = utils.get_users()
    for user in users:
        utils.update_user_stats_cache(user['panel_id'])
    stats.cleanup_json_cache(force=True)
    log_cron(cron_uid, "DONE updating users stats cache")

@uwsgidecorators.timer(33 * 60)
def periodic_health_check_parse(signal):
    cron_uid = 'periodic_health_check_parse_' + str(random.randint(0, 1000000))
    log_cron(cron_uid, "Health check parse")
    health_check.parse()
    health_check.update_health_cache()
    log_cron(cron_uid, "DONE health check parse")

@uwsgidecorators.cron(-10, -1, -1, -1, -1)
def save_connected_ips(signal):
    cron_uid = 'save_connected_ips_' + str(random.randint(0, 1000000))
    log_cron(cron_uid, "Saving connected IPs")
    stats.save_connected_ips_count()
    log_cron(cron_uid, "DONE saving connected IPs")

@uwsgidecorators.lock
@uwsgidecorators.thread
def update_certificates():
    cron_uid = 'update_certificates_' + str(random.randint(0, 1000000))
    log_cron(cron_uid, "Updating certificates")
    domains = utils.get_domains()
    domains.append(config.get_panel_domain())

    needs_reload = False
    for domain in domains:
        log_cron(cron_uid, "Updating certificate for " + domain)
        result = certbot.generate_certificate(domain, retry=False, reload_haproxy=False)
        log_cron(cron_uid, "Result for " + domain + ": " + result)
        if result in ['success', 'failed_but_changed']:
            needs_reload = True
    
    if needs_reload:
        log_cron(cron_uid, "Reloading HAProxy")
        sysops.haproxy_reload()
    else:
        log_cron(cron_uid, "No need to reload HAProxy")

    log_cron(cron_uid, "DONE updating certificates")

@uwsgidecorators.cron(-5, -1, -1, -1, -1)
def update_certificates_cron(signal):
    update_certificates()

@uwsgidecorators.signal(config.SIGNAL_INVALIDATE_CACHE, target='workers')
def invalidate_caches(signum):
    log_cron('invalidate_caches', "Invalidating caches")
    utils.invalidate_user_configuration_cache()
    stats.cleanup_json_cache(force=True)
    log_cron('invalidate_caches', "DONE invalidating caches")

def create_app():
    app = Flask(__name__)

    print("Updating HAProxy lists")
    sysops.haproxy_update_users_list()
    sysops.haproxy_update_domains_list()
    sysops.haproxy_update_camouflage_list()

    if settings.get_migration_counter() <= 1:
        for domain in utils.get_domains():
            settings.all_domains_ever_push(domain)
        settings.set_migration_counter(2)
    
    if settings.get_migration_counter() <= 2:
        try:
            sysops.regenerate_camouflage_cert()
        except Exception as e:
            print("Failed to regenerate camouflage cert: " + str(e))
        settings.set_migration_counter(3)
            

    domains_count = len(utils.get_domains())
    users_count = len(utils.get_users())
    if users_count == 0:
        print("No users, will create the first one")
        # No users, create the first one
        utils.create_user('Libertea user')

    if domains_count == 0:
        print("No domains, will create the first one")
        domain = config.get_panel_domain()
        utils.add_domain(domain)
        threading.Thread(target=utils.update_domain_cache, args=(domain, 2)).start()

    try:
        sysops.regenerate_camouflage_cert()
        # update_certificates()
        health_check.update_health_cache()
    except:
        traceback.print_exc()
        pass

    print("Starting the app")
    app.register_blueprint(admin.blueprint)
    app.register_blueprint(user.blueprint)
    app.register_blueprint(api.blueprint)
    app.register_blueprint(welcome.blueprint)

    return app
