# -*- coding: utf-8 -*-

# For debugging
# NVIM_PYTHON_LOG_FILE=nvim.log NVIM_PYTHON_LOG_LEVEL=INFO nvim

import os
import re
import logging
import jedi
import copy
from neovim import attach, setup_logging

logger = logging.getLogger(__name__)

class Handler:

    name = 'cm-core'

    def __init__(self,nvim):
        self._nvim = nvim

        # { '{source_name}': {'startcol': , 'matches'}
        self._matches = {}
        self._sources = {}

    def cm_complete(self,srcs,name,ctx,startcol,matches,*args):
        self._sources = srcs

        # store matches
        if name not in self._matches:
            self._matches[name] = {}
        if len(matches)==0:
            del self._matches[name]
        else:
            self._matches[name]['startcol'] = startcol
            self._matches[name]['matches'] = matches

        self._refresh_completions(ctx)

    def cm_insert_enter(self):
        self._matches = {}
        # self._refresh_completions(self,ctx):


    # The completion core itself
    def cm_refresh(self,srcs,ctx,*args):

        self._sources = srcs

        # simple complete done
        if ctx['typed'] == '':
            self._matches = {}
        elif re.match(r'[^0-9a-zA-Z_]',ctx['typed'][-1]):
            self._matches = {}

        self._refresh_completions(ctx)

    def _refresh_completions(self,ctx):

        matches = []

        # sort by priority
        names = sorted(self._matches.keys(),key=lambda x: self._sources[x]['priority'], reverse=True)

        if len(names)==0:
            logger.info('_refresh_completions names: %s, startcol: %s, matches: %s', names, ctx['col'], matches)
            self._nvim.call('cm#core_complete', ctx, ctx['col'], [], self._matches, async=True)
            return

        startcol = min([self._matches[name]['startcol'] for name in names])
        base = ctx['typed'][startcol-1:]

        for name in names:

            try:
                curstartcol = self._matches[name]['startcol']
                curmatches = self._matches[name]['matches']
                if curstartcol>ctx['col']:
                    logger.error('wrong startcol: %s', self._matches[name])
                    continue
                prefix = ctx['typed'][startcol-1 : curstartcol-1]
                for item in curmatches:

                    e = {}
                    if type(item)==type(''):
                        e['word'] = prefix+item
                    else:
                        e = copy.deepcopy(item)

                    if 'menu' not in e:
                        e['menu'] = self._sources[name].get('abbreviation','')

                    # do the same word filtering as vim's doing
                    if base.lower() != e['word'][0:len(base)].lower():
                        continue

                    matches.append(e)
            except Exception as inst:
                logger.error('_refresh_completions process exception: %s', inst)
                continue

        logger.info('_refresh_completions names: %s, startcol: %s, matches: %s', names, startcol, matches)
        self._nvim.call('cm#core_complete', ctx, startcol, matches, self._matches, async=True)

def main():

    # logging setup
    level = logging.INFO
    if 'NVIM_PYTHON_LOG_LEVEL' in os.environ:
        # TODO this affects the log file name
        setup_logging('cm-core')
        l = getattr(logging,
                os.environ['NVIM_PYTHON_LOG_LEVEL'].strip(),
                level)
        if isinstance(l, int):
            level = l
    logger.setLevel(level)

    # connect neovim
    nvim = attach('stdio')
    nvim_event_loop(nvim)

def nvim_event_loop(nvim):

    handler = Handler(nvim)

    def on_setup():
        logger.info('on_setup')

    def on_request(method, args):
        raise Exception('Not implemented')

    def on_notification(method, args):
        nonlocal handler
        logger.info('method: %s, args: %s', method, args)

        func = getattr(handler,method,None)
        if func is None:
            return

        func(*args)

    nvim.run_loop(on_request, on_notification, on_setup)

main()
