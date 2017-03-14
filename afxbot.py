#!/usr/bin/env python3
## coding=UTF-8
#
# AFX_bot: a simple Telegram bot in Python
# Copyright (C) 2016 Anfauglir Kz. <anfauglirkz@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

class WashSnake:
    """
    This object describes a anti-flood stat for given user.

    Attributes:
        firsttime (datetime):
        content (str):
        responded (bool):

        repeattimes (Optional[int]):
    """

    def __init__(self,
                 firsttime,
                 content,
                 repeattimes=0):
        self.firsttime = firsttime
        self.content = content

        self.responded = False
        self.repeattimes = repeattimes


class AFXBot:
    """
    This object represents a working Telegram bot.


    Arguments:
    conf_file_name (Optional[str]):
        Name of configuration file.
    """

    def __init__(self,
                 conf_file_name = None,
                 **kwargs):
        # Base. ;)
        self.LAST_UPDATE_ID = None
        self.NOW_HANDLING_UPDATE_ID = None
        self.logger = logging.getLogger()
        self.bot = None
        self.motds = None
        self.config = None
        self.strs = None

        # Keyword and Symptom lists.
        self.kw_list = None
        self.kw_list_get = None
        self.symptom_tbl = None
        self.symptom_get = None

        # Unified with symptom entries.
        self.unified_kw_list = None
        self.unified_get_list = None

        # Bot state
        self.is_running = True
        self.is_accepting_photos = False

        # For wash snake
        self.wash_record = dict()

        # Hardcoded fortune...
        self.fortune_strs = ['大凶', '凶', '平', '小吉', '大吉']
        self.fortune_types = { '大前天': -3, '大後天': 3, \
                             '前天': -2, '昨日': -1, '昨天': -1, \
                             '今日': 0, '今天': 0,
                             '明日': 1, '明天': 1, '後天': 2}

        self.fortune_keys = sorted(self.fortune_types.keys(), \
                      key = lambda x: len(x), reverse = True)
        # Hardcoded Strings...
        self.wash_snake_strs_unified = None
        self.log_fmt_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Parse command line params
        arg_parser = argparse.ArgumentParser(description = 'AFX_bot, a simple Telegram bot in Python.')
        arg_parser.add_argument('-l', '--logfile', help='Logfile Name', action='store_true')

        args = arg_parser.parse_args()

        if args.logfile:
            logging.basicConfig( level=logging.DEBUG, format=self.log_fmt_str, filename=args.logfile)
        else:
            logging.basicConfig( level=logging.DEBUG, format=self.log_fmt_str)

        self.logger = logging.getLogger('AFX_bot')
        self.logger.setLevel(logging.DEBUG)

        self.init_configuration(conf_file_name)
        self.init_l10n_strings()
        self.init_motd()

        # Telegram Bot Authorization Token
        self.bot = telegram.Bot(self.config['bot_token'])

        self.register_callbacks()

        self.recognition_list = []

    def init_hanbao_pet_properties(self, 
	                               file_name = None):
        if not file_name:
            file_name = 'hanbao_pet.json'

        try:
            with open(file_name, 'r', encoding = 'utf8') as f:
                self.config = json.loads(f.read())

            # Check Configuration
            #configs_check = ['bot_token', 'resp_db', 'adm_ids', 'operational_chats', 'strings_json']
            #for c in configs_check:
            #    self.checkConfigEntry(c)

            #list_configs_check = ['restricted_chats', 'motd_only_chats', 'invasive_washsnake_chats']
            #for c in list_configs_check:
            #    self.checkConfigEntryOfList(c)

        except FileNotFoundError:
            logging.exception('hanbao_pet file not found!')
        except ValueError:
            logging.exception('hanbao_pet read error.')
        except:
            raise

    def init_configuration(self,
                           file_name):
        """
        Initialize configuration.

        Arguments:
            file_name (str):
                Name of configuration file.
        """
        # Load Configuration
        if not file_name:
            file_name = 'config.json'

        try:
            with open(file_name, 'r', encoding = 'utf8') as f:
                self.config = json.loads(f.read())

            # Check Configuration
            configs_check = ['bot_token', 'resp_db', 'adm_ids', 'operational_chats', 'strings_json']
            for c in configs_check:
                self.check_config_entry(c)

            list_configs_check = ['restricted_chats', 'motd_only_chats', 'invasive_washsnake_chats']
            for c in list_configs_check:
                self.check_config_entry_of_list(c)

            self.init_resp()
        except FileNotFoundError:
            logging.exception('config file not found!')
            raise
        except ValueError:
            logging.exception('config read error or item missing!')
            raise
        except:
            raise

    def init_l10n_strings(self,
                          file_name = None):
        """
        Initialize L10N strings.

        Arguments:
            file_name (Optional[str]):
                Name of L10N strings file.
        """
        # Load L10N Strings (forced now)
        if not file_name:
            file_name = self.config['strings_json']
            if not file_name:
                raise Exception('L10N file not specified in neither config nor argument!')

        try:
            with open(self.config['strings_json'], 'r', encoding = 'utf8') as f:
                self.strs = json.loads(f.read())
                self.wash_snake_strs_unified = self.strs['r_wash_snake_strs'] + self.strs['r_invasive_wash_snake_strs']
        except:
            logging.exception('L10N Strings read error!')
            raise

    def init_motd(self,
                  file_name = 'motd.json'):
        """
        Initialize MotD.

        Arguments:
            file_name (Optional[str]):
                Name of MotD file.
        """
        # Load MotD
        try:
            with open(file_name, 'r', encoding = 'utf8') as f:
                self.motds = json.loads(f.read())

            # str -> datetime
            for k in self.motds.keys():
                self.motds[k]['date'] = datetime.strptime(self.motds[k]['date'], '%Y-%m-%d').date()

        except FileNotFoundError:
            logging.exception('MOTD file not found!')
        except ValueError:
            logging.exception('MOTD read error!')
        except:
            raise

        if not self.motds:
            self.motds = dict()

    def check_config_entry(self,
                           name):
        """
        Check whether the config is sane.
        """
        if not self.config[name]:
            logging.error('config[\'{0}\'] is missing!')
            raise ValueError

    def check_config_entry_of_list(self,
                                   name):
        """
        Check whether the list in config is sane, or init a empty one.
        """
        if not self.config[name]:
            self.config[name] = []

    def run(self):
        """
        Run the bot: start the loop to fetch updates and handle.
        """
        self.get_latest_update_id()
        self.recoverStatus = False

        while True:
            # This will be our global variable to keep the latest update_id when requesting
            # for updates. It starts with the latest update_id if available.
            try:
                if self.recoverStatus:
                    # try to reinit...
                    self.bot = telegram.Bot(self.config['bot_token'])
                    self.get_latest_update_id()
                    self.recoverStatus = False

                self.get_mesg()
            except KeyboardInterrupt:
                exit()
            except http.client.HTTPException:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()
            except urllib.error.HTTPError:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()
            except Exception as ex:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')
                self.recover()

    def recover(self):
        """
        Recover the bot in next loop.
        """
        self.recoverStatus = True
        if self.NOW_HANDLING_UPDATE_ID:
            self.LAST_UPDATE_ID = self.NOW_HANDLING_UPDATE_ID + 1
        else:
            self.LAST_UPDATE_ID = self.LAST_UPDATE_ID + 1

    def json_serial(self,
                    obj):
        """
        Returns:
            String-serialized datetime or date object.
        """
        if isinstance(obj, datetime):
            serial = obj.isoformat()
            return serial

        if isinstance(obj, date):
            serial = obj.isoformat()
            return serial
        raise TypeError ("Type not serializable")

    def get_latest_update_id(self):
        """
        Get latest update id from Telegram server.
        Gonna ignore all previous updates... ;)
        """
        try:
            updates = self.bot.getUpdates(timeout = 10)
            self.logger.debug('update length: {0}'.format(len(updates)))
            if len(updates) == 1:
                self.LAST_UPDATE_ID = updates[-1].update_id
            else:
                while(len(updates) > 1):
                    self.LAST_UPDATE_ID = updates[-1].update_id
                    updates = self.bot.getUpdates(offset=self.LAST_UPDATE_ID+1, timeout = 10)
                    self.logger.debug('update length: {0}'.format(len(updates)))
        except:
            self.logger.exception('!!! Get Last update ID Error !!!')

    def init_resp(self):
        """
        Read all keywords/symptoms from self.resp_db.
        """
        self.logger.debug('Initializing response...')
        self.resp_db = sqlite3.connect(self.config['resp_db'])
        self.resp_db.row_factory = sqlite3.Row
        c = self.resp_db.cursor()

        self.kw_list = list()
        c.execute('SELECT keyword FROM resp GROUP BY keyword ORDER BY RANDOM() DESC;')
        for kw in c:
            self.kw_list.append(kw['keyword'])

        self.kw_list_get = list()
        c.execute('SELECT keyword FROM resp_get GROUP BY keyword ORDER BY RANDOM() DESC;')
        for kw in c:
            self.kw_list_get.append(kw['keyword'])

        self.symptom_tbl = dict()
        c.execute('SELECT before, after FROM symptom ORDER BY LENGTH(before) DESC;')
        for syms in c:
            self.symptom_tbl[syms['before']] = syms['after']

        self.symptom_get = dict()
        c.execute('SELECT before, after FROM symptom_get ORDER BY LENGTH(before) DESC;')
        for syms in c:
            self.symptom_get[syms['before']] = syms['after']


        self.unified_kw_list = self.kw_list + list(self.symptom_tbl.keys())
        self.unified_get_list = self.kw_list_get + list(self.symptom_get.keys())

    def send_generic_mesg(self,
                          chat_id,
                          text,
                          reply_to_message_id = None):
        """
        For sending simple messages only including text (in most cases.)
        """
        self.bot.sendMessage(chat_id = chat_id, text = text, reply_to_message_id = reply_to_message_id)

    def get_mesg(self):
        """
        Fetch updates from server for further processes.
        """
        # Request updates after the last updated_id
        for update in self.bot.getUpdates(offset=self.LAST_UPDATE_ID, timeout=10):
            self.logger.info('Update: ' + str(update));
            # chat_id is required to reply any message
            chat_id = update.message.chat_id
            message = update.message.text
            mesg_id = update.message.message_id
            user_id = update.message.from_user.id
            self.NOW_HANDLING_UPDATE_ID = update.update_id

            self.logger.debug('now handling update: {0}'.format(self.NOW_HANDLING_UPDATE_ID))
            
            try:
                if message:
                    # YOU SHALL NOT PASS!
                    # Only authorized group chats and users (admins) can access this bot.
                    if not self.do_augmented_auth(update.message.chat.id):
                        if '__FOR_RECOGNITION__' in message and not update.message.chat.id in self.recognition_list:
                            self.send_generic_mesg(chat_id, 'Please contact moderator to add following id into ACL.')
                            self.send_generic_mesg(chat_id, str(update.message.chat.id))
                            self.recognition_list.append(update.message.chat.id)
                        else:
                            self.logger.info('Access denied from: ' + str(update.message.chat.id))

                    elif self.handle_washsnake(update):
                        nothing_todo = 1

                    # Status querying.
                    elif self.strs['q_status_kw'] in message:
                        if self.is_running:
                            self.send_generic_mesg(chat_id, self.strs['qr_status_t'], mesg_id)
                        else:
                            self.send_generic_mesg(chat_id, self.strs['qr_status_f'], mesg_id)

                    # Only admins can re-enable bot.
                    elif not self.is_running and message.startswith(self.strs['s_status_t_kw']) and self.do_adm_auth(user_id):
                        self.send_generic_mesg(chat_id, self.strs['sr_status_t_ok'], mesg_id)
                        self.init_resp()
                        self.is_running = True

                    # MOTDs are necessary.
                    elif message.lower().startswith('/motd') or self.is_handle_motd(message):
                        self.handle_motd(update)

                    # Only MOTD for some special groups, otherwise...
                    elif self.is_running and self.do_operational_auth(update.message.chat.id):
                        # Batch update *.jpg in /images/
                        if message.startswith(self.strs['v_photo_bulkupload']) and self.do_adm_auth(user_id):
                            p = Path('images')
                            fl = list(p.glob('*.jpg'))
                            if len(fl) == 0:
                                self.send_generic_mesg(chat_id, self.strs['vr_photo_bulkupload_no_file'], mesg_id)
                            else:
                                for image_name in fl:
                                    # for uploading new photos
                                    with open(str(image_name), 'rb') as nn:
                                        photo_res = self.bot.sendPhoto(chat_id = chat_id, photo = nn)

                                    photo_mesg = photo_res.photo[-1].file_id
                                    self.send_generic_mesg(chat_id, photo_mesg, photo_res.message_id)


                        # Reload keyword table
                        # Disable bot
                        # Enter/Exit photo upload mode
                        # Handle ADM cmd/Common cmd/Fortune tell
                        elif self.execute_callbacks(self.bot_callbacks, update):
                            nothing_todo = 1

                        # other...
                        else:
                            self.handle_response(update)
                    elif self.is_running and update.message.chat.id in self.config['restricted_chats']:
                        if self.execute_callbacks(self.bot_callbacks_restricted, update):
                            nothing_todo = 1
                    elif self.is_running:
                        self.logger.debug('Not handling, in motd_only chats?')
                    else:
                        self.logger.debug('Not running...')

                # upload photo, adm only
                elif update.message.photo and self.is_accepting_photos and self.do_adm_auth(user_id):
                    try:
                        self.logger.debug('PhotoContent: ' + update.message.photo[-1].file_id);
                        photo_mesg = update.message.photo[-1].file_id
                        photo_res = self.bot.sendPhoto(chat_id = chat_id, photo = photo_mesg)
                        photo_mesg = photo_res.photo[-1].file_id
                        self.send_generic_mesg(chat_id, photo_mesg, photo_res.message_id)
                    except:
                        nothing_todo = 1

                #else:
                #    self.logger.debug('NotHandleContent: ' + str(update.message));
            except:
                if chat_id != None and mesg_id != None:
                    self.send_generic_mesg(chat_id, self.append_more_smiles('好像哪裡怪怪der '), mesg_id)
                    
                self.logger.exception('')

            # Updates global offset to get the new updates
            self.LAST_UPDATE_ID = self.NOW_HANDLING_UPDATE_ID + 1

    def is_handle_motd(self,
                       mesg):
        """
        Returns:
            True when strings in self.strs['q_motd_kws'] found in mesg, otherwise False.
        """
        for m in self.strs['q_motd_kws']:
            if m in mesg:
                return True
        return False

    def match_fortune_type(self,
                           mesg):
        """
        Returns:
            Strings in self.fortune_types found in mesg, otherwise None.
        """

        for fs in self.fortune_keys:
            if (fs + '運勢') in mesg:
                return fs
        return None

    def do_adm_auth(self,
                    id):
        """
        Returns:
            Presence of id in self.config['adm_ids'].
        """
        return id in self.config['adm_ids']

    def do_operational_auth(self,
                            id):
        """
        Returns:
            Presence of id in self.config['operational_chats'],
                              self.config['adm_ids']
        """
        return id in self.config['operational_chats'] \
               or id in self.config['adm_ids']

    def do_augmented_auth(self,
                          id):
        """
        Returns:
            Presence of id in self.config['operational_chats'],
                              self.config['adm_ids'],
                              self.config['restricted_chats'],
                              or self.config['motd_only_chats'].
        """
        return id in self.config['operational_chats'] \
               or id in self.config['adm_ids'] \
               or id in self.config['restricted_chats'] \
               or id in self.config['motd_only_chats']

    def append_more_smiles(self,
                           str,
                           rl = 1,
                           ru = 3):
        """
        Returns:
            str with smiles in amount of random(rl, ru) appended on the tail.
        """
        return str + '\U0001F603' * random.randint(rl, ru)

    def handle_adm_cmd(self,
                                         update):
        """
        Handles all administrative commands.

        Args:
            update (telegram.update):
                Update object to handle.
        """
        chat_id = update.message.chat_id
        mesg = update.message.text.strip()
        mesg_id = update.message.message_id

        cmd_toks = [x.strip() for x in mesg.split(' ')]
        while '' in cmd_toks:
            cmd_toks.remove('')

        cmd_entity = cmd_toks[1].lower()

        c = self.resp_db.cursor()
        self.logger.debug('cmd_entity: ' + cmd_entity)


        # 憨包來吃圖
        if cmd_entity == 'begin_get':
            self.set_is_accepting_photos(True)

        # 憨包吃飽沒
        elif cmd_entity == 'end_get':
            self.set_is_accepting_photos(False)

        elif cmd_entity == 'mk_get':
            # for multi-group.
            gid = chat_id
            if gid > 0:
                gid = -1
                
            pic_id = cmd_toks[2]
            kw = cmd_toks[3].lower()
            if len(cmd_toks) > 4:
                tag = cmd_toks[4].lower()
            else:
                tag = None
            try:
                self.logger.debug('Photo ID = ' + cmd_toks[2])
                photo_res = self.bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = cmd_toks[2]);
                if kw in self.symptom_get.keys():
                    self.send_generic_mesg(chat_id, '({0} -> {1}) => {2}'.format(kw, self.symptom_get[kw], pic_id), photo_res.message_id)
                    kw = self.symptom_get[kw]
                else:
                    self.send_generic_mesg(chat_id, '{0}    => {1}'.format(kw, pic_id), photo_res.message_id)

                c.execute('''INSERT INTO resp_get (keyword, cont, tag, gid) VALUES (?, ?, ?, ?) ''', ( kw, pic_id, tag, gid))
                self.resp_db.commit()
                self.init_resp()
            except TelegramError:
                self.send_generic_mesg(chat_id, 'ERROR ON : {0} => {1}'.format(kw, pic_id), photo_res.message_id)

        elif cmd_entity == 'getpic_id':
            pic_id = cmd_toks[2]

            try:
                photo_res = self.bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = pic_id);
            except TelegramError:
                self.send_generic_mesg(chat_id, 'ERROR ON : {0}'.format(pic_id), photo_res.message_id)

        elif cmd_entity == 'ed_get':
            not_implemented = 1

        # make get symptom -> keyword
        elif cmd_entity == 'mk_get_sym':
            if len(cmd_toks) > 3:
                kw_before = cmd_toks[2].lower()
                kw_after = cmd_toks[3].lower()
            else:
                not_implemented = 1

        # list /get kw
        elif cmd_entity == 'ls_get':
            if len(cmd_toks) > 2:
                outmesg = ''
                kw = cmd_toks[2].lower()

                if kw in self.symptom_get.keys():
                    outmesg += '({0} -> {1}) => \n'.format(kw, self.symptom_get[kw])
                    kw = self.symptom_get[kw]
                else:
                    outmesg += '{0} => \n'.format(kw)

                c.execute('''SELECT IIDX, cont, tag FROM resp_get WHERE keyword = ? ORDER BY IIDX ASC;''', (kw, ))
                for conts in c:
                    if not conts['tag']:
                        outmesg += '/getid_' + str(conts['IIDX']) + ' : ' + conts['cont'][:8] + '...' + conts['cont'][-8:] + ' (N/A)\n'
                    else:
                        outmesg += '/getid_' + str(conts['IIDX']) + ' : ' + conts['cont'][:8] + '...' + conts['cont'][-8:] + '(' + conts['tag'] + ')\n'

                self.send_generic_mesg(chat_id, outmesg, mesg_id)

            else: 
                outmesg = 'Supported /get keywords:\n'
                s_keys = self.symptom_get.keys()
                for kw in self.unified_get_list:

                    if kw in s_keys:
                        outmesg = outmesg + kw + ' -> ' + self.symptom_get[kw] + '\n'
                    else:
                        outmesg = outmesg + kw + '\n'

                self.send_generic_mesg(chat_id, outmesg, mesg_id)

        # make keyword -> content
        # ^/adm\s+mk_kw\s+([^\s]+)\s+(.+)$
        elif cmd_entity == 'mk_kw':
            if len(cmd_toks) > 3:
                kw = cmd_toks[2].lower()
                content = mesg[(mesg.find(cmd_toks[2]) + len(cmd_toks[2]) + 1):].strip()

                if kw in self.symptom_tbl.keys():
                    self.send_generic_mesg(chat_id, '({0} -> {1}) => {2}'.format(kw, self.symptom_tbl[kw], content), mesg_id)
                    kw = self.symptom_tbl[kw]
                else:
                    self.send_generic_mesg(chat_id, '{0}    => {1}'.format(kw, content), mesg_id)

                c.execute('''INSERT INTO resp (keyword, cont) VALUES (?, ?) ''', ( kw, content, ))
                self.resp_db.commit()
                self.init_resp()
            else:
                self.send_generic_mesg(chat_id, 'arglist err.', mesg_id)

        # make symptom -> keyword
        # ^/adm\s+mk_sym\s+([^\s]+)\s+([^\s]+).*$
        elif cmd_entity == 'mk_sym':
            if len(cmd_toks) > 3:
                kw_before = cmd_toks[2].lower()
                kw_after = cmd_toks[3].lower()

                if kw_before in self.symptom_tbl.keys():
                    self.send_generic_mesg(chat_id, 'Already exists: ({0} -> …) => …'.format(kw_before), mesg_id)
                elif kw_before in self.kw_list:
                    self.send_generic_mesg(chat_id, 'Already exists: {0} => …'.format(kw_before), mesg_id)
                else:
                    self.send_generic_mesg(chat_id, '{0}    => {1}'.format(kw_before, kw_after), mesg_id)
                    c.execute('''INSERT INTO symptom (before, after) VALUES (?, ?) ''', ( kw_before, kw_after, ))
                    self.resp_db.commit()
                    self.init_resp()
            else:
                self.send_generic_mesg(chat_id, 'arglist err.', mesg_id)

         # make symptom -> keyword
        # ^/adm\s+mk_sym\s+([^\s]+)\s+([^\s]+).*$
        elif cmd_entity == 'mk_get_sym':
            if len(cmd_toks) > 3:
                kw_before = cmd_toks[2].lower()
                kw_after = cmd_toks[3].lower()

                self.send_generic_mesg(chat_id, 'Not implemented.\n({0} -> {1}) => …'.format(kw_before, kw_after), mesg_id)
            else:
                self.send_generic_mesg(chat_id, 'arglist err.', mesg_id)

        # todo: assign index for each kw -> cont pair.
        elif cmd_entity == 'rm_kw':
            if len(cmd_toks) > 2:
                try:
                    to_rm = int(cmd_toks[2].lower())

                    c.execute('''DELETE FROM resp WHERE IIDX = ? ''', ( to_rm, ))
                    self.resp_db.commit()
                    self.init_resp()

                    self.send_generic_mesg(chat_id, str(to_rm) + ' deleted.', mesg_id)

                except ValueError:
                    self.send_generic_mesg(chat_id, 'arg err.', mesg_id)

            else:
                self.send_generic_mesg(chat_id, 'arglist err.', mesg_id)
                
        elif cmd_entity == 'rm_get':
            if len(cmd_toks) > 2:
                try:
                    to_rm = int(cmd_toks[2].lower())

                    c.execute('''DELETE FROM resp_get WHERE IIDX = ? ''', ( to_rm, ))
                    self.resp_db.commit()
                    self.init_resp()

                    self.send_generic_mesg(chat_id, str(to_rm) + ' deleted.', mesg_id)

                except ValueError:
                    self.send_generic_mesg(chat_id, 'arg err.', mesg_id)

            else:
                self.send_generic_mesg(chat_id, 'arglist err.', mesg_id)

        elif cmd_entity == 'rm_get_sym':
            not_implemented = 1

        # list keyword
        elif cmd_entity == 'ls_kw':
            s_keys = self.symptom_tbl.keys()
            if len(cmd_toks) > 2:
                outmesg = ''

                kw = cmd_toks[2].lower()
                if kw in self.symptom_get.keys():
                    outmesg += '({0} -> {1}) => \n'.format(kw, self.symptom_tbl[kw])
                    kw = self.symptom_tbl[kw]
                else:
                    outmesg += '{0} => \n'.format(kw)

                c.execute('''SELECT IIDX, cont FROM resp WHERE keyword = ? ORDER BY IIDX ASC;''', (kw, ))
                for conts in c:
                    outmesg += str(conts['IIDX']) + '. ' + conts['cont'] + '\n'

                self.send_generic_mesg(chat_id, outmesg, mesg_id)

            else:
                outmesg = 'Supported keywords:\n'
                for kw in self.unified_kw_list:

                    if kw in s_keys:
                        outmesg = outmesg + kw + ' -> ' + self.symptom_tbl[kw] + '\n'
                    else:
                        outmesg = outmesg + kw + '\n'

                self.send_generic_mesg(chat_id, outmesg, mesg_id)

        else:
            self.send_generic_mesg(chat_id, 'adm what? owo', mesg_id)

    def handle_cmd(self,
                   update):
        """
        Handles all common commands.

        Args:
            update (telegram.update):
                Update object to handle.
        Returns:
            True when the command is handled, otherwise False.
        """
        chat_id = update.message.chat_id
        restricted = not self.do_operational_auth(chat_id)
        mesg = update.message.text
        mesg_id = update.message.message_id
        mesg_low = mesg.lower().replace('@afx_bot', '')

        cmd_toks = [x.strip() for x in mesg.split(' ')]
        while '' in cmd_toks:
            cmd_toks.remove('')

        if mesg_low.startswith('/get ') and not restricted:
            keyword = cmd_toks[1].lower()

            if len(cmd_toks) > 2:
                tag = cmd_toks[2].lower()
                self.logger.debug('keyword: ' + keyword)
                self.logger.debug('tag: ' + tag)
            else:
                tag = None
                self.logger.debug('keyword: ' + keyword)

            if keyword in self.symptom_get.keys():
                keyword = self.symptom_get[keyword]

            if keyword in self.kw_list_get:
                c = self.resp_db.cursor()
                x = None

                if tag :
                    c.execute('''SELECT cont FROM resp_get WHERE keyword = ? AND tag = ? ORDER BY RANDOM() LIMIT 1;''', ( keyword, tag, ))
                    x = c.fetchone()

                if not x:
                    c.execute('''SELECT cont FROM resp_get WHERE keyword = ? ORDER BY RANDOM() LIMIT 1;''', ( keyword, ))
                    x = c.fetchone()

                if x:
                    self.bot.sendPhoto(chat_id = chat_id, reply_to_message_id = mesg_id, photo = str(x['cont']));
                else:
                    self.send_generic_mesg(chat_id, 'Something goes wrong! D:', mesg_id)
            else:
                self.send_generic_mesg(chat_id, self.append_more_smiles('You get nothing! '), mesg_id)

            return True

        # Get picture directly by given resp ID.
        elif mesg_low.startswith('/getid') and not restricted:
            if len(cmd_toks) > 1:
                res_get_id = cmd_toks[1]
            else:
                res_get_id = mesg_low[7:]

            c = self.resp_db.cursor()
            c.execute('''SELECT cont FROM resp_get WHERE IIDX = ? LIMIT 1;''', (res_get_id,))
            x = c.fetchone()

            if x:
                self.bot.sendPhoto(chat_id=chat_id, reply_to_message_id=mesg_id, photo=str(x['cont']));
            else:
                self.send_generic_mesg(chat_id, self.append_more_smiles('You get nothing! '), mesg_id)

            return True

        elif mesg == '/roll@AFX_bot':
            self.send_generic_mesg(chat_id, self.strs['r_roll_cmd_help'], mesg_id)
            return True

        elif mesg_low.startswith('/roll ') or mesg_low == '/roll':
            return self.handle_roll(update)

        elif mesg == '/crash':
            raise Exception('Crash!')
            
        return False

    def handle_response(self,
                      update):
        """
        Handles all typical responses.

        Args:
            update (telegram.update):
                Update object to handle.
        Returns:
            True when the command is handled, otherwise False.
        """
        chat_id = update.message.chat_id
        mesg = update.message.text
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id
        mesg_low = mesg.lower()

        # hardcoded...
        if    'ass' in mesg_low and not 'pass' in mesg_low:
            self.send_generic_mesg(chat_id, 'Ood', mesg_id)
            return True

        if    user_id == 99786298 and chat_id == -1001069764018:
            self.send_generic_mesg(chat_id, '喔喔', mesg_id)
            return True

        if ('蕉姐' in mesg_low or '蕉姊' in mesg_low or '香蕉' in mesg_low) and ('幾' in mesg_low or '多少' in mesg_low) :
            self.send_generic_mesg(chat_id, '3064', mesg_id)
            return True


        random.shuffle(self.unified_kw_list)
        s_keys = self.symptom_tbl.keys()

        # convert kw
        for kw in self.unified_kw_list:
            if kw in mesg_low:
                if kw in s_keys:
                    unified_kw = self.symptom_tbl[kw]
                    self.logger.debug('keyword: ' + kw + ' -> ' + unified_kw)
                else:
                    unified_kw = kw
                    self.logger.debug('keyword: ' + kw )

                c = self.resp_db.cursor()
                c.execute('''SELECT cont FROM resp WHERE keyword = ? ORDER BY RANDOM() LIMIT 1;''', ( unified_kw, ))
                x = c.fetchone()
                self.send_generic_mesg(chat_id, str(x['cont']), mesg_id)
                return True

        return False

    def handle_roll(self,
                                    update):
        """
        Handles /roll commands.

        Args:
            update (telegram.update):
                Update object to handle.
        """
        chat_id = update.message.chat_id
        mesg_low = update.message.text.lower()
        mesg_id = update.message.message_id

        if mesg_low == '/roll':
            d_cmd = ''
        else:
            d_cmd = mesg_low[6:].strip()

        # XdYsZ
        res = re.match('([0-9]+)d([0-9]+)s([0-9]+)', d_cmd)
        if res:
            dn = int(res.group(1))
            dt = int(res.group(2))
            ds = int(res.group(3))
            dstr = '('
            succ = 0

            if dn > 100: dn = 100

            for i in range(dn):
                val = random.randint(1, dt)
                if val >= ds: succ += 1
                dstr += str(val) + ', '

            dstr = '{0}d{1}s{2} : {3}) >= {2}, 成功 {4} 次'.format(dn, dt, ds, dstr[:-2], succ);
            self.send_generic_mesg(chat_id, dstr, mesg_id)
            return True

        # XdY[+-Z]
        res = re.match('([0-9]+)d([0-9]+)([+-][0-9]+)?', d_cmd)
        if res:
            dn = int(res.group(1))
            dt = int(res.group(2))
            if res.group(3):
                dm = int(res.group(3))
            else:
                dm =    0;

            dstr = '('
            sum = 0

            if dn > 100: dn = 100

            for i in range(dn):
                val = random.randint(1, dt)
                sum += val
                dstr += str(val) + ', '

            if dm == 0:
                dstr = '{0}d{1} : {2}) = {3}'.format(dn, dt, dstr[:-2], sum);
            else:
                if dm > 0:
                    dm_str = '+' + str(dm)
                else:
                    dm_str = str(dm)
                dstr = '{0}d{1}{2} : {3}) {2} = {4} {2} = {5}'.format(dn, dt, dm_str, dstr[:-2], sum, sum+dm);
            self.send_generic_mesg(chat_id, dstr, mesg_id)
            return True

        # X[-Y]
        res = re.match('([0-9]+)(-([0-9]+))?', d_cmd)
        if res:
            if res.group(3):
                dl = int(res.group(1))
                du = int(res.group(3))
            else:
                dl = 1
                du = int(res.group(1))
                
            if dl > du:
                self.send_generic_mesg(chat_id, self.strs['r_roll_cmd_help'], mesg_id)
            else:
                dstr = 'roll ({1}-{2}): {0}'.format(random.randint(dl, du), dl, du);
                self.send_generic_mesg(chat_id, dstr, mesg_id)

            return True

        # default 1-100
        if d_cmd == '':
            dstr = 'roll (1-100): {0} '.format(random.randint(1,100));
            self.send_generic_mesg(chat_id, dstr, mesg_id)
            return True

        # Syntax error, sending help.
        else:
            self.send_generic_mesg(chat_id, self.strs['r_roll_cmd_help'], mesg_id)
            return True

    def handle_fortune_tell(self,
                              update):
        """
        Handles fortune tell requests.

        Args:
            update (telegram.update):
                Update object to handle.
        """
        chat_id = update.message.chat_id
        mesg = update.message.text
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id
        type = self.match_fortune_type(mesg)

        md5 = hashlib.md5()

        fortune_date = date.today()
        date_offset = self.fortune_types[type]
        if date_offset >= 0:
            fortune_date = fortune_date+timedelta(days=date_offset)
        else:
            fortune_date = fortune_date-timedelta(days=(-date_offset))

        f_data = bytearray(str(user_id) + datetime.strftime(fortune_date, self.strs['x_fortune_salt_str']), 'utf-8')

        md5.update(f_data)
        fstr = '{0}運勢：{1}'.format(type, self.fortune_strs[int(md5.digest()[12]) % len(self.fortune_strs)])
        self.send_generic_mesg(chat_id, fstr, mesg_id)


    def handle_motd(self,
                                    update):
        """
        Handles MotD query and update requests.

        Args:
            update (telegram.update):
                Update object to handle.
        """
        chat_id = update.message.chat_id
        mesg_id = update.message.message_id

        if chat_id > 0:
            self.send_generic_mesg(chat_id, 'MotD Function is for groups only.', mesg_id)
            return

        mesg = update.message.text.replace('@afx_bot', '')
        mesg_low = mesg.lower()

        schat_id = str(chat_id)
        motd_update_match_res = re.match('^/motd[\s\n]+(.+)', mesg, re.IGNORECASE | re.DOTALL)

        if mesg_low == '/motd':    # print motd
            self.send_motd(chat_id, mesg_id)
        elif motd_update_match_res:
            motd_cmd = motd_update_match_res.group(1).strip()

            if not schat_id in self.motds.keys():
                self.motds[schat_id] = dict()

            self.motds[schat_id]['msg'] = motd_cmd
            self.motds[schat_id]['date'] = date.today()

            today_str = datetime.strftime(self.motds[schat_id]['date'], '%Y-%m-%d')
            self.logger.info('MOTD: \n'+self.motds[schat_id]['msg'])

            try:
                self.logger.info('writing MOTD contents')
                with open('motd.json', 'w') as f:
                    json.dump(self.motds, f, default=self.json_serial)
                    f.close()
            except Exception as ex:
                logging.exception('!!! EXCEPTION HAS OCCURRED !!!')

            self.send_generic_mesg(chat_id, self.strs['r_motd_updated'].format(date = today_str), mesg_id)
        else:
            for m in self.strs['q_motd_kws']:
                if m in mesg:
                    self.send_motd(chat_id, mesg_id)

    def send_motd(self,
                                chat_id,
                                mesg_id):
        """
        Send MotD content to given chat or user.

        Args:
            chat_id (int):
                Unique identifier for the message recipient - telegram.User or telegram.GroupChat id.
            mesg_id (int):
                Message ID of given update to handle.
        """
        schat_id = str(chat_id)

        if schat_id in self.motds.keys():
            motd_date_str = datetime.strftime(self.motds[schat_id]['date'], '%Y-%m-%d')
        else:
            motd_date_str = '????-??-??'

        if not schat_id in self.motds.keys():
            self.send_generic_mesg(chat_id, self.strs['r_motd_no'], mesg_id)
        elif self.motds[schat_id]['date'] != date.today():
            self.send_generic_mesg(chat_id, self.strs['r_motd_old'].format(date = motd_date_str, motd = self.motds[schat_id]['msg']), mesg_id)
        else:
            self.send_generic_mesg(chat_id, self.strs['r_motd_ok'].format(date = motd_date_str, motd = self.motds[schat_id]['msg']), mesg_id)

    def handle_washsnake(self,
                         update):
        """
        Handles anti-flood responses.

        Args:
            update (telegram.update):
                Update object to handle.

        Returns:
            True when anti-flood response is sent, otherwise False.
        """
        # Must convert id's into string for dict storage.
        chat_id = update.message.chat_id
        message = update.message.text
        date = update.message.date
        mesg_id = update.message.message_id
        user_id = update.message.from_user.id

        schat_id = str(chat_id)
        suser_id = str(user_id)
        washsnake_content = message.lower().strip()
        if not str(chat_id) in self.wash_record.keys():
            self.wash_record[schat_id] = dict()

        # random angry...
        if random.randint(1, 1000) >= 995 and chat_id in self.config['invasive_washsnake_chats']:
            self.logger.debug('random angry triggered for {0} - {1}'.format(chat_id, mesg_id))
            self.send_generic_mesg(chat_id, random.choice(self.strs['r_invasive_random_angry_strs']), mesg_id)
        elif not suser_id in self.wash_record[schat_id].keys():
            self.logger.debug('new washsnake content for ' + suser_id)
            self.wash_record[schat_id][suser_id] = WashSnake(date, washsnake_content)
        else:
            # check
            washsnake_entry = self.wash_record[schat_id][suser_id];
            if washsnake_entry.content == washsnake_content:
                # same content, check time
                time_delta = date - washsnake_entry.firsttime
                self.logger.debug('washsnake_entry.firsttime = ' + str(washsnake_entry.firsttime))
                self.logger.debug('date = ' + str(date))
                self.logger.debug('time_delta = ' + str(time_delta))

                if time_delta < timedelta(seconds=60):
                    self.logger.debug('wash ++ for ' + str(update.message))
                    self.wash_record[schat_id][suser_id].repeattimes += 1;
                    if washsnake_entry.repeattimes >= 2:
                        if not washsnake_entry.responded:
                            # WASH SNAKE!!
                            if chat_id in self.config['invasive_washsnake_chats'] or self.do_adm_auth(user_id):
                                self.send_generic_mesg(chat_id, random.choice(self.wash_snake_strs_unified), mesg_id)
                            else:
                                self.send_generic_mesg(chat_id, random.choice(self.strs['r_wash_snake_strs']), mesg_id)
                            self.wash_record[schat_id][suser_id].responded = True

                        return True
                else:
                    # reset wash snake counter...
                    self.wash_record[schat_id][suser_id].responded = False
                    self.wash_record[schat_id][suser_id].firsttime = update.message.date
                    self.wash_record[schat_id][suser_id].repeattimes = 0
            else:
                self.logger.debug('update wash for ' + suser_id)
                self.wash_record[schat_id][suser_id] = WashSnake(update.message.date, washsnake_content)

        return False

    def set_is_running(self,
                                         flag):
        """Assign flag to is_running."""
        self.is_running = flag

    def set_is_accepting_photos(self,
                                      flag):
        """Assign flag to is_accepting_photos."""
        self.is_accepting_photos = flag

    @staticmethod
    def execute_callbacks(bcblist,
                          update):
        """Run registered callbacks."""
        for bcb in bcblist:
            if bcb.execute(update):
                return True
        return False

    def register_callbacks(self):
        """Register callbacks."""

        # For restricted chats, only restricted commands and fortune teller works.
        self.bot_callbacks_restricted = [
            self.BotCallback('call_cmd_handler_bcb',
                             self,
                             {'q_kw': '/'},
                             False,
                             lambda update: self.handle_cmd(update)),

            self.BotCallback('call_fortune_teller_bcb',
                             self,
                             { },
                             False,
                             lambda update: self.handle_fortune_tell(update),
                             lambda update: self.match_fortune_type(update.message.text))
        ]

        # For regular chats.
        self.bot_callbacks = [
            self.BotCallback('reload_kw_bcb',
                             self,
                             {'q_kw': self.strs['a_reload_kwlist_kw'],
                              'r_ok': self.strs['ar_reload_kwlist_ok'],
                              'r_ng': self.strs['ar_reload_kwlist_ng']},
                             True,
                             lambda update: self.init_resp()),

            self.BotCallback('set_running_f_bcb',
                             self,
                             {'q_kw': self.strs['s_status_f_kw'],
                              'r_ok': self.strs['sr_status_f_ok'],
                              'r_ng': self.strs['sr_status_f_ng']},
                             True,
                             lambda update: self.set_is_running(False)),

            self.BotCallback('set_imgupload_t_bcb',
                             self,
                             {'q_kw': self.strs['s_imgupload_t_kw'],
                              'r_ok': self.strs['sr_imgupload_t_ok'],
                              'r_ng': self.strs['sr_imgupload_t_ng']},
                             True,
                             lambda update: self.set_is_accepting_photos(True)),

            self.BotCallback('set_imgupload_f_bcb',
                             self,
                             {'q_kw': self.strs['s_imgupload_f_kw'],
                              'r_ok': self.strs['sr_imgupload_f_ok'],
                              'r_ng': self.strs['sr_imgupload_f_ng']},
                             True,
                             lambda update: self.set_is_accepting_photos(False)),

            self.BotCallback('call_adm_cmd_handler_bcb',
                             self,
                             {'q_kw': '/adm'},
                             True,
                             lambda update: self.handle_adm_cmd(update)),

            self.BotCallback('call_cmd_handler_bcb',
                             self,
                             {'q_kw': '/'},
                             False,
                             lambda update: self.handle_cmd(update)),

            self.BotCallback('call_fortune_teller_bcb',
                             self,
                             { },
                             False,
                             lambda update: self.handle_fortune_tell(update),
                             lambda update: self.match_fortune_type(update.message.text))
        ]


    class BotCallback:
        """
        This object describes a conditional callback.

        Execute handler when given keyword is found in given update.

        Attributes:
            name (str):
                Name of this callback
            bot (Telegram.bot):
                Bot to handle requests
            need_adm (bool):
                Indicates that the handler needs administrator privilege to run.
            strs (dict):
                Dict to record strings.
                'q_kw': Keyword to match in message text.
                'r_ok': Response message when the handler ran successfully.
                'r_ng': Response message when the handler encountered permssion denied.
            handler_callback (func(update)):
                The Handler that will be called.
            cond_callback (Optional[func(update)]):
                The callback function will be called for checking whether to run or not.
        """

        def __init__(self,
                     name,
                     bot,
                     strs,
                     need_adm,
                     handler_callback,
                     cond_callback = None,):
            self.name = name
            self.bot = bot
            self.strs = strs
            self.need_adm = need_adm
            self.handler_callback = handler_callback
            self.cond_callback = cond_callback


        def execute(self, update):
            """Execute defined callback function."""
            mesg = update.message.text
            chat_id = update.message.chat_id
            mesg_id = update.message.message_id
            user_id = update.message.from_user.id

            if 'q_kw' in self.strs.keys():
                cond = mesg.startswith(self.strs['q_kw'])
            else:
                cond = self.cond_callback(update)

            if cond:
                if (self.bot.do_adm_auth(user_id) and self.need_adm) or not self.need_adm:
                    if self.handler_callback:
                        self.handler_callback(update)

                    if 'r_ok' in self.strs.keys():
                        self.bot.send_generic_mesg(chat_id, self.strs['r_ok'], mesg_id)

                    return True
                else:
                    if 'r_ok' in self.strs.keys():
                        self.bot.send_generic_mesg(chat_id, self.strs['r_ng'], mesg_id)

                    return True
            else:
                return False

def main():
    bot = AFXBot('config.json')
    bot.run()

if __name__ == '__main__':
    main()
