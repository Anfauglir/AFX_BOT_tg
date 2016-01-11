#!/usr/bin/env python3
# coding=UTF-8

__author__ = 'Anfauglir'

# TODO:
# 1. anti-flood timer.
# 2. REize all command handler.  (optional)

import logging
import telegram
import re
import random
import json
import sqlite3
import string
import http
import hashlib
import urllib
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path


# Base. ;)
LAST_UPDATE_ID = None
logger = logging.getLogger()
bot = None
motds = None
config = None
strs = None

# Keyword and Sympotom lists.
kw_list = None
kw_list_get = None
symptom_tbl = None
symptom_get = None

# Unified with symptom entries.
unified_kw_list = None
unified_get_list = None

# Bot state
is_running = True
is_accepting_photos = False

# For wash snake
wash_record = dict()

# Hardcoded fortune...
fortune_strs = ['大凶', '凶', '平', '小吉', '大吉']
fortune_types = ['昨日', '今日', '明日']

# Hardcoded Strings...
wash_snake_strs_unified = None
log_fmt_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

gnn_washsnake = None

# For serialize date/datetime into string.
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial

    if isinstance(obj, date):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

class WashSnake:
    def __init__(self, firsttime, content, **kwargs):
        self.firsttime = firsttime
        self.content = content

        self.responded = False
        self.repeattimes = kwargs.get('repeattimes')
        if self.repeattimes == None:
            self.repeattimes = 0

# Gonna ignore all previous updates... ;)
def getLatestUpdateId():
    global LAST_UPDATE_ID, bot

    try:
        LAST_UPDATE_ID = bot.getUpdates(timeout = 10)[-1].update_id
        LAST_UPDATE_ID = bot.getUpdates(offset=LAST_UPDATE_ID, timeout = 10)[-1].update_id
    except:
        logging.exception('!!! Get Last update ID Error !!!')
        LAST_UPDATE_ID = None

# If snake is None, initialize a empty list.
def cheakAndInitEmptyList(snake):
    if(snake == None):
        return []
    else:
        return snake

def main():
    global logger, config, bot, strs
    global LAST_UPDATE_ID, motds, resp_db
    global log_fmt_str
    global gnn_washsnake, wash_snake_strs_unified

    # Parse command line params
    arg_parser = argparse.ArgumentParser(description = 'AFX_bot, a simple Telegram bot in Python.')
    arg_parser.add_argument('-l', '--logfile', help='Logfile Name', action='store_true')

    args = arg_parser.parse_args()

    if(args.logfile):
        logging.basicConfig( level=logging.DEBUG, format=log_fmt_str, filename=args.logfile)
    else:
        logging.basicConfig( level=logging.DEBUG, format=log_fmt_str)

    logger = logging.getLogger('AFX_bot')
    logger.setLevel(logging.DEBUG)

    # initialization
    try:
        with open('config.json', 'r', encoding = 'utf8') as f:
            config = json.loads(f.read())

        # check configurations
        if(config['bot_token'] == None
            or config['resp_db'] == None
            or config['adm_ids'] == None
            or config['strings_json'] == None):
            raise ValueError

        config['limited_chats'] = cheakAndInitEmptyList(config['limited_chats'])
        config['only_motd'] = cheakAndInitEmptyList(config['only_motd'])

        initResp()
    except FileNotFoundError:
        logging.exception('config file not found!')
        raise
    except ValueError:
        logging.exception('config read error or item missing!')
        raise
    except:
        raise
        
    try:
        with open(config['strings_json'], 'r', encoding = 'utf8') as f:
            strs = json.loads(f.read())
            
            wash_snake_strs_unified = strs['r_wash_snake_strs'] + strs['r_invasive_wash_snake_strs']
    except:
        logging.exception('L10N Strings read error!')
        raise
        
    # Telegram Bot Authorization Token
    bot = telegram.Bot(config['bot_token'])

    try:
        with open('motd.json', 'r', encoding = 'utf8') as f:
            motds = json.loads(f.read())

        # str -> datetime
        for k in motds.keys():
            motds[k]['date'] = datetime.strptime(motds[k]['date'], '%Y-%m-%d').date()

    except FileNotFoundError:
        logging.exception('MOTD file not found!')
    except ValueError:
        logging.exception('MOTD read error!')
    except:
        raise
        
    try:
        with open('gnn_washsnake.json', 'r') as f:
            gnn_json = json.loads(f.read(), encoding='utf-8')
            
        if(gnn_json['gnn_washsnake'] != None):
            gnn_washsnake = gnn_json['gnn_washsnake']
                
    except FileNotFoundError:
        logging.exception('gnn_washsnake file not found!')
    except ValueError:
        logging.exception('gnn_washsnake read error!')
    except:
        do_nothing = 1

    getLatestUpdateId()

    recoverStatus = False

    while True:
        # This will be our global variable to keep the latest update_id when requesting
        # for updates. It starts with the latest update_id if available.
        try:
            if(recoverStatus == True):
                # try to reinit...
                bot = telegram.Bot(config['bot_token'])
                getLatestUpdateId()
                recoverStatus = False

            getMesg()
        except KeyboardInterrupt:
            exit()
        except http.client.HTTPException:
            logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
            recoverStatus = True
        except urllib.error.HTTPError:
            logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
            recoverStatus = True
        except Exception as ex:
            logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
            recoverStatus = True

# Read all keywords/symptoms from resp_db.
def initResp():
    global logger, resp_db
    global kw_list, kw_list_get, symptom_tbl, symptom_get, unified_kw_list, unified_get_list

    resp_db = sqlite3.connect(config['resp_db'])
    resp_db.row_factory = sqlite3.Row
    c = resp_db.cursor()

    kw_list = list()
    c.execute('SELECT keyword FROM resp GROUP BY keyword ORDER BY RANDOM() DESC;')
    for kw in c:
        kw_list.append(kw['keyword'])

    kw_list_get = list()
    c.execute('SELECT keyword FROM resp_get GROUP BY keyword ORDER BY RANDOM() DESC;')
    for kw in c:
        kw_list_get.append(kw['keyword'])

    symptom_tbl = dict()
    c.execute('SELECT before, after FROM symptom ORDER BY LENGTH(before) DESC;')
    for syms in c:
        symptom_tbl[syms['before']] = syms['after']

    symptom_get = dict()
    c.execute('SELECT before, after FROM symptom_get ORDER BY LENGTH(before) DESC;')
    for syms in c:
        symptom_get[syms['before']] = syms['after']


    unified_kw_list = kw_list + list(symptom_tbl.keys())
    unified_get_list = kw_list_get + list(symptom_get.keys())

# For sending simple messages only including text (in most cases.)
def sendGenericMesg(chat_id, mesg_id, text):
    global bot
    bot.sendMessage(chat_id = chat_id, text = text, reply_to_message_id = mesg_id)

# Fetch updates from server for further processes.
def getMesg():
    global logger, bot, strs
    global LAST_UPDATE_ID, is_running, is_accepting_photos, wash_record, wash_snake_strs_unified
    global gnn_washsnake
    
    # Request updates after the last updated_id
    for update in bot.getUpdates(offset=LAST_UPDATE_ID, timeout=10):
        # chat_id is required to reply any message
        chat_id = update.message.chat_id
        message = update.message.text
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id

        if (message):
            # YOU SHALL NOT PASS!
            # Only authorized group chats and users (admins) can access this bot.
            if(not doAuthWithGroups(update.message.chat.id)):
                logger.debug('Access denied from: ' + str(update.message.chat.id))
                LAST_UPDATE_ID = update.update_id + 1
                continue

            # Wash snake... Must convert id's into string for dict storage.
            schat_id = str(chat_id)
            suser_id = str(user_id)
            washsnake_content = message.lower().strip()
            if(not str(chat_id) in wash_record.keys()):
                wash_record[schat_id] = dict()

            if(not suser_id in wash_record[schat_id].keys()):
                logger.debug('new washsnake content for ' + suser_id)
                wash_record[schat_id][suser_id] = WashSnake(update.message.date, washsnake_content)
            else:
                # check
                washsnake_entry = wash_record[schat_id][suser_id];
                if(washsnake_entry.content == washsnake_content):
                    # same content, check time
                    time_delta = washsnake_entry.firsttime - update.message.date
                    if(time_delta < timedelta(seconds=60)):
                        logger.debug('wash ++ for ' + str(update.message))
                        wash_record[schat_id][suser_id].repeattimes += 1;
                        if(washsnake_entry.repeattimes >= 2):
                            if(not washsnake_entry.responded):
                                # WASH SNAKE!!
                                if(chat_id in gnn_washsnake or doAuth(user_id)):
                                    sendGenericMesg(chat_id, mesg_id, random.choice(wash_snake_strs_unified))
                                else:
                                    sendGenericMesg(chat_id, mesg_id, random.choice(strs['r_wash_snake_strs']))
                                wash_record[schat_id][suser_id].responded = True

                            LAST_UPDATE_ID = update.update_id + 1
                            continue
                    else:
                        # reset wash snake counter...
                        wash_record[schat_id][suser_id].responded = False
                        wash_record[schat_id][suser_id].firsttime = update.message.date
                        wash_record[schat_id][suser_id].repeattimes = 0
                else:
                    logger.debug('update wash for ' + suser_id)
                    wash_record[schat_id][suser_id] = WashSnake(update.message.date, washsnake_content)

            # Status querying.
            if (strs['q_status_kw'] in message):
                if(is_running):
                    sendGenericMesg(chat_id, mesg_id, strs['qr_status_t'])
                else:
                    sendGenericMesg(chat_id, mesg_id, strs['qr_status_f'])

            # Only admins can re-enable bot.
            elif (not is_running and message.startswith(strs['s_status_t_kw']) and doAuth(user_id)):
                sendGenericMesg(chat_id, mesg_id, strs['sr_status_t_ok'])
                initResp()
                is_running = True

            # MOTDs are necessary.
            elif (message.lower().startswith('/motd') or '本日重點' in message or '今日重點' in message or '今天重點' in message):
                doHandleMotd(chat_id, message, mesg_id)

            # Only MOTD for some special groups, otherwise...
            elif (is_running and not chat_id in config['only_motd']):
                # Batch update *.jpg in /images/
                if (message.startswith('照片GOGO') and doAuth(user_id)):
                    p = Path('images')
                    fl = list(p.glob('*.jpg'))
                    if(len(fl) == 0):
                        sendGenericMesg(chat_id, mesg_id, '/images/裡頭，沒圖沒真相...')
                    else:
                        for image_name in fl:
                            # for uploading new photos
                            with open(str(image_name), 'rb') as nn:
                                photo_res = bot.sendPhoto(chat_id = chat_id, photo = nn)

                            photo_mesg = photo_res.photo[-1].file_id
                            sendGenericMesg(chat_id, photo_res.message_id, photo_mesg)

                # Reload keyword table etc...
                elif (message.startswith(strs['a_reload_kwlist_kw'])):
                    if(doAuth(user_id)):
                        initResp()
                        sendGenericMesg(chat_id, mesg_id, strs['ar_reload_kwlist_ok'])
                    else:
                        sendGenericMesg(chat_id, mesg_id, strs['ar_reload_kwlist_ng'])

                # Disable bot
                elif (message.startswith(strs['s_status_f_kw'])):
                    if(doAuth(user_id)):
                        sendGenericMesg(chat_id, mesg_id, strs['sr_status_f_ok'])
                        is_running = False
                    else:
                        sendGenericMesg(chat_id, mesg_id, strs['sr_status_f_ng'])

                # Enter photo upload mode
                elif (message.startswith(strs['s_imgupload_t_kw'])):
                    if(doAuth(user_id)):
                        sendGenericMesg(chat_id, mesg_id, strs['sr_imgupload_t_ok'])
                        is_accepting_photos = True
                    else:
                        sendGenericMesg(chat_id, mesg_id, strs['sr_imgupload_t_ng'])

                # Enter photo upload mode
                elif (message.startswith(strs['s_imgupload_f_kw'])):
                    if(doAuth(user_id)):
                        sendGenericMesg(chat_id, mesg_id, strs['sr_imgupload_f_ok'])
                        is_accepting_photos = False
                    else:
                        sendGenericMesg(chat_id, mesg_id, strs['sr_imgupload_f_ng'])

                # Handle ADM commands
                elif (message.startswith('/adm') and doAuth(user_id)):
                    doHandleAdmCmd(chat_id, message, mesg_id)

                # Handle commands
                elif (message.startswith('/')):
                    doHandleCmd(chat_id, message, mesg_id)

                # Fortune teller
                elif (matchFortuneType(message) != None):
                    doHandleFortuneTell(chat_id, user_id ,mesg_id, matchFortuneType(message))

                # other...
                else:
                    doHandleResponse(chat_id, message, mesg_id, user_id)
            elif (is_running):
                # Handle commands
                if (message.startswith('/')):
                    doHandleCmd(chat_id, message, mesg_id, True)

                # Fortune teller
                elif (matchFortuneType(message) != None):
                    doHandleFortuneTell(chat_id, user_id ,mesg_id, matchFortuneType(message))
            else:
                logger.debug('Not running...')

        # upload photo, adm only
        elif (update.message.photo != None and is_accepting_photos and doAuth(user_id)):
            try:
                logger.debug('PhotoContent: ' + update.message.photo[-1].file_id);
                photo_mesg = update.message.photo[-1].file_id
                photo_res = bot.sendPhoto(chat_id = chat_id, photo = photo_mesg)
                photo_mesg = photo_res.photo[-1].file_id
                sendGenericMesg(chat_id, photo_res.message_id, photo_mesg)
            except:
                nothing_todo = 1

        #else:
        #    logger.debug('NotHandleContent: ' + str(update.message));

        # Updates global offset to get the new updates
        LAST_UPDATE_ID = update.update_id + 1

def matchFortuneType(mesg):
    global fortune_types
    for fs in fortune_types:
        if (fs + '運勢') in mesg:
            return fs

    return None

def doAuth(id):
    return id in config['adm_ids']

def doAuthWithGroups(cid):
    if len(config['limited_chats']) == 0:
        return id in config['adm_ids']
    else:
        return cid in config['limited_chats'] or cid in config['adm_ids']

def appendMoreSmile(str, rl = 1, ru = 3):
    return str + '\U0001F603' * random.randint(rl, ru)

def doHandleAdmCmd(chat_id, mesg, mesg_id):
    global logger, bot
    global resp_db, kw_list, kw_list_get, is_accepting_photos
    global unified_kw_list, unified_get_list

    cmd_toks = [x.strip() for x in mesg.split(' ')]
    cmd_entity = cmd_toks[1].lower()

    c = resp_db.cursor()
    logger.debug('cmd_entity: ' + cmd_entity)

    ### for /get
    # 憨包來吃圖
    if(cmd_entity == 'begin_get'):
        is_accepting_photos = True

    # 憨包吃飽沒
    elif(cmd_entity == 'end_get'):
        is_accepting_photos = False

    elif(cmd_entity == 'mk_get'):
        id = cmd_toks[2]
        kw = cmd_toks[3].lower()
        if (len(cmd_toks) > 4):
            tag = cmd_toks[4]
        else:
            tag = None
        try:
            photo_res = bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = cmd_toks[2]);
            if(kw in symptom_get.keys()):
                sendGenericMesg(chat_id, photo_res.message_id, '({0} -> {1}) => {2}'.format(kw, symptom_get[kw], id))
                kw = symptom_get[kw]
            else:
                sendGenericMesg(chat_id, photo_res.message_id, '{0}  => {1}'.format(kw, id))

            c.execute('''INSERT INTO resp_get (keyword, cont, tag) VALUES (?, ?, ?) ''', ( kw, id, tag, ))
            resp_db.commit()
            initResp()
        except TelegramError:
            sendGenericMesg(chat_id, photo_res.message_id, 'ERROR ON : {1} => {2}'.format(kw, id))

    elif(cmd_entity == 'getpic'):
        id = cmd_toks[2]

        try:
            photo_res = bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = id);
        except TelegramError:
            sendGenericMesg(chat_id, photo_res.message_id, 'ERROR ON : {1}'.format(id))

    elif(cmd_entity == 'ed_get'):
        not_implemented = 1

    # make get symptom -> keyword
    elif(cmd_entity == 'mk_get_sym'):
        if(len(cmd_toks) > 3):
            kw_before = cmd_toks[2].lower()
            kw_after = cmd_toks[3].lower()
        else:
            not_implemented = 1

    # list /get kw
    elif(cmd_entity == 'ls_get'):
        if(len(cmd_toks) > 2):
            outmesg = ''
            kw = cmd_toks[2].lower()

            if(kw in symptom_tbl.keys()):
                outmesg += '({0} -> {1}) => \n'.format(kw, symptom_tbl[kw])
                kw = symptom_tbl[kw]
            else:
                outmesg += '{0} => \n'.format(kw)
            
            c.execute('''SELECT cont, tag FROM resp_get WHERE keyword = ? ORDER BY IIDX DESC;''', (kw, ))
            for conts in c:
                if conts['tag'] == None :
                    outmesg += conts['cont'] + ' (N/A)\n'
                else:
                    outmesg += conts['cont'] + ' (' + conts['tag'] + ')\n'

            sendGenericMesg(chat_id, mesg_id, outmesg)

        else:
            outmesg = 'Supported /get keywords:\n'
            s_keys = symptom_get.keys()
            for kw in unified_get_list:

                if (kw in s_keys):
                    outmesg = outmesg + kw + ' -> ' + symptom_get[kw] + '\n'
                else:
                    outmesg = outmesg + kw + '\n'

            sendGenericMesg(chat_id, mesg_id, outmesg )

    ### for typical conversation
    # nothing yet
    # make keyword -> content
    # ^/adm\s+mk_kw\s+([^\s]+)\s+(.+)$
    elif(cmd_entity == 'mk_kw'):
        if(len(cmd_toks) > 3):
            kw = cmd_toks[2].lower()
            content = cmd_toks[3]

            if(kw in symptom_tbl.keys()):
                sendGenericMesg(chat_id, mesg_id, '({0} -> {1}) => {2}'.format(kw, symptom_tbl[kw], content))
                kw = symptom_tbl[kw]
            else:
                sendGenericMesg(chat_id, mesg_id, '{0}  => {1}'.format(kw, content))

            c.execute('''INSERT INTO resp (keyword, cont) VALUES (?, ?) ''', ( kw, content, ))
            resp_db.commit()
        else:
            not_implemented = 1

    # make symptom -> keyword
    # ^/adm\s+mk_sym\s+([^\s]+)\s+([^\s]+).*$
    elif(cmd_entity == 'mk_sym'):
        if(len(cmd_toks) > 3):
            kw_before = cmd_toks[2].lower()
            kw_after = cmd_toks[3].lower()

            sendGenericMesg(chat_id, mesg_id, '({0} -> {1}) => …'.format(kw_before, kw_after))
        else:
            not_implemented = 1

    # todo: assign index for each kw -> cont pair.
    elif(cmd_entity == 'rm_kw'):
        not_implemented = 1

    elif(cmd_entity == 'rm_get_sym'):
        not_implemented = 1

    # list keyword
    elif(cmd_entity == 'ls_kw'):
        s_keys = symptom_tbl.keys()
        if(len(cmd_toks) > 2):
            outmesg = ''
            if (not kw in s_keys):
                kw = cmd_toks[2].lower()

            c.execute('''SELECT cont FROM resp WHERE keyword = ? ORDER BY IIDX DESC;''', (kw, ))
            for conts in c:
                outmesg += conts['cont'] + '\n'


            sendGenericMesg(chat_id, mesg_id, kw + ' => \n' + outmesg )

        else:
            outmesg = 'Supported keywords:\n'
            for kw in unified_kw_list:

                if (kw in s_keys):
                    outmesg = outmesg + kw + ' -> ' + symptom_tbl[kw] + '\n'
                else:
                    outmesg = outmesg + kw + '\n'

            sendGenericMesg(chat_id, mesg_id, outmesg )

    else:
        sendGenericMesg(chat_id, mesg_id, 'adm what? owo'  )

def doHandleCmd(chat_id, mesg, mesg_id, restricted = False): 
    global logger, bot
    global resp_db, kw_list, kw_list_get
    global unified_kw_list
    mesg_low = mesg.lower().replace('@afx_bot', '')

    if (mesg_low.startswith('/get ') and not restricted):
        keyword = mesg_low[5:].strip()
        logger.debug('keyword: ' + keyword)

        if (keyword in symptom_get.keys()):
            keyword = symptom_get[keyword]

        if (keyword in kw_list_get):
            c = resp_db.cursor()
            c.execute('''SELECT cont FROM resp_get WHERE keyword = ? ORDER BY RANDOM() LIMIT 1;''', ( keyword, ))
            x = c.fetchone()
            bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = str(x['cont']));
        else:
            sendGenericMesg(chat_id, mesg_id, appendMoreSmile('You get nothing! '))

        return True

    elif (mesg == '/roll@AFX_bot'):
        sendGenericMesg(chat_id, mesg_id, '/roll [ 最大值 (1000) | 最小值-最大值 (20-30) | 骰數d骰面[+-調整值] (2d6, 1d20+12) | 骰數d骰面s成功值 (2d6s4) ]')
        return True

    elif (mesg_low.startswith('/roll ') or mesg_low == '/roll'):
        return doHandleRoll(chat_id, mesg_low, mesg_id)

    return False

def doHandleResponse(chat_id, mesg, mesg_id, user_id):
    global logger, bot
    global resp_db, symptom_tbl, unified_kw_list
    mesg_low = mesg.lower()

    # hardcoded...
    if ( 'ass' in mesg_low and not 'pass' in mesg_low):
        sendGenericMesg(chat_id, mesg_id, 'Ood')
        return True

    if ('阿倫' in mesg):
        sendGenericMesg(chat_id, mesg_id, appendMoreSmile('你需要更多的ㄅㄊ '))
        return True

    random.shuffle(unified_kw_list)
    s_keys = symptom_tbl.keys()

    # convert kw
    for kw in unified_kw_list:
        if kw in mesg_low:
            if (kw in s_keys):
                unified_kw = symptom_tbl[kw]
                logger.debug('keyword: ' + kw + ' -> ' + unified_kw)
            else:
                unified_kw = kw
                logger.debug('keyword: ' + kw )

            c = resp_db.cursor()
            c.execute('''SELECT cont FROM resp WHERE keyword = ? ORDER BY RANDOM() LIMIT 1;''', ( unified_kw, ))
            x = c.fetchone()
            sendGenericMesg(chat_id, mesg_id, str(x['cont']))
            return True

    return False

def doHandleRoll(chat_id, mesg_low, mesg_id):
    global bot

    if (mesg_low == '/roll'):
        d_cmd = ''
    else:
        d_cmd = mesg_low[6:].strip()

    res = re.match('([0-9]+)d([0-9]+)s([0-9]+)', d_cmd)
    if (res):
        dn = int(res.group(1))
        dt = int(res.group(2))
        ds = int(res.group(3))
        dstr = '('
        succ = 0

        if(dn > 100): dn = 100

        for i in range(dn):
            val = random.randint(1, dt)
            if (val >= ds): succ += 1
            dstr += str(val) + ', '

        dstr = '{0}d{1}s{2} : {3}) >= {2}, 成功 {4} 次'.format(dn, dt, ds, dstr[:-2], succ);
        sendGenericMesg(chat_id, mesg_id, dstr)
        return True

    res = re.match('([0-9]+)d([0-9]+)([+-][0-9]+)?', d_cmd)
    if (res):
        dn = int(res.group(1))
        dt = int(res.group(2))
        if (res.group(3) != None) :
            dm = int(res.group(3))
        else:
            dm =  0;

        dstr = '('
        sum = 0

        if(dn > 100): dn = 100

        for i in range(dn):
            val = random.randint(1, dt)
            sum += val
            dstr += str(val) + ', '

        if (dm == 0):
            dstr = '{0}d{1} : {2}) = {3}'.format(dn, dt, dstr[:-2], sum);
        else:
            if (dm > 0):
                dm_str = '+' + str(dm)
            else:
                dm_str = str(dm)
            dstr = '{0}d{1}{2} : {3}) {2} = {4} {2} = {5}'.format(dn, dt, dm_str, dstr[:-2], sum, sum+dm);
        sendGenericMesg(chat_id, mesg_id, dstr)
        return True

    res = re.match('([0-9]+)(-([0-9]+))?', d_cmd)
    if (res):
        if (res.group(3) != None):
            dl = int(res.group(1))
            du = int(res.group(3))
        else:
            dl = 1
            du = int(res.group(1))

        dstr = '你擲出了: {0} ({1}-{2})'.format(random.randint(dl, du), dl, du);
        sendGenericMesg(chat_id, mesg_id, dstr)
        return True

    if (d_cmd == ''):
        dstr = '你擲出了: {0} (1-100)'.format(random.randint(1,100));
        sendGenericMesg(chat_id, mesg_id, dstr)
        return True

    else:
        sendGenericMesg(chat_id, mesg_id, '/roll [ 最大值 (1000) | 最小值-最大值 (20-30) | 骰數d骰面[+-調整值] (2d6, 1d20+12) | 骰數d骰面s成功值 (2d6s4) ]')
        return True

def doHandleFortuneTell(chat_id, target_id, message_id, type):
    global bot, fortune_strs
    md5 = hashlib.md5()

    format_str = '^_^ANFAUGLIR_SALT##$$%Y__??__%m__!!__%d**&&ANFAUGLIR_SALT^_^'

    fortune_date = date.today()
    if(type == '明日'):
        fortune_date = fortune_date+timedelta(days=1)
    elif (type == '昨日'):
        fortune_date = fortune_date-timedelta(days=1)

    f_data = bytearray(str(target_id) + datetime.strftime(fortune_date, format_str), 'utf-8')

    md5.update(f_data)
    fstr = '{0}運勢：{1}'.format(type, fortune_strs[int(md5.digest()[12]) % len(fortune_strs)])
    sendGenericMesg(chat_id, message_id, fstr)



def doHandleMotd(chat_id, mesg, mesg_id):
    global bot, motds
    mesg_low = mesg.lower().replace('@afx_bot', '')
    mesg = mesg.replace('@afx_bot', '')
    schat_id = str(chat_id)

    if(mesg_low.startswith('/motd')):
        if(mesg_low == '/motd'):  # print motd
            printMotd(chat_id, mesg_id)
        else:
            motd_cmd = mesg[5:].strip()
            if(not schat_id in motds.keys()):
                motds[schat_id] = dict()

            motds[schat_id]['msg'] = motd_cmd
            motds[schat_id]['date'] = date.today()

            today_str = datetime.strftime(motds[schat_id]['date'], '%Y-%m-%d')
            logger.info('MOTD: \n'+motds[schat_id]['msg'])

            try:
                logger.info('writing MOTD contents')
                with open('motd.json', 'w') as f:
                    json.dump(motds, f, default=json_serial)
                    f.close()
            except Exception as ex:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')

            sendGenericMesg(chat_id, mesg_id, strs['r_motd_updated'].format(date = today_str))
    elif (mesg_low == '/motd' or '本日重點' in mesg_low or '今日重點' in mesg_low or '今天重點' in mesg_low):
        printMotd(chat_id, mesg_id)
    else:
        logging.debug('wtf?!')

def printMotd(chat_id, mesg_id):
    global bot, motds, strs
    schat_id = str(chat_id)

    if(schat_id in motds.keys()):
        motd_date_str = datetime.strftime(motds[schat_id]['date'], '%Y-%m-%d')
    else:
        motd_date_str = '????-??-??'

    if(not schat_id in motds.keys()):
        sendGenericMesg(chat_id, mesg_id, strs['r_motd_no'])
    if (motds[schat_id]['date'] != date.today()):
        sendGenericMesg(chat_id, mesg_id, strs['r_motd_old'].format(date = motd_date_str, motd = motds[schat_id]['msg']))
    else:
        sendGenericMesg(chat_id, mesg_id, strs['r_motd_ok'].format(date = motd_date_str, motd = motds[schat_id]['msg']))

if __name__ == '__main__':
    main()