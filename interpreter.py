from datetime import datetime
from rich.console import Console
from aliases import aliases
import logging
import pytz
import re


class Signal():

	'''
	Signal object. The most important part about this class is the "flag" attribute. 
	This is responsible for how the other application will use the signal:
	- limit: contains info to execute a limit order
	- market: contains info to execute a market order
	- no-data: this is a signal but there's something missing (includes errors)
	- update-tp: this contains info to modify the tps of a certain position
	- partials: signals to take partials on a position
	- close: signals to close a position
	- message: just a normal message
	'''

	def __init__(self,
				 text: str,
				 time: datetime,
				 localize_tz: pytz.timezone = pytz.timezone('Europe/Rome')):
		
		self.text = text
		self.tz = localize_tz
		self.time = localize_tz.localize(time) if time.tzinfo is None else time
		self.ticker = None
		self.sl = None
		self.entry = None
		self.side = None
		self.flag = None
		self.tp = []

	def add_tp(self, tp):

		if not isinstance(tp, list):
			tp = list(tp)

		for tp_str in tp:
			
			tp_f = round(float(tp_str), 5)
			# check for validity of tp 
			# (must be after the entry) and sort
			if self.side == 'buy':
				if self.entry and (tp_f < self.entry):
					continue
				self.tp.append(tp_f)
				self.tp = sorted(list(set(self.tp)))
			
			else:
				if self.entry and (tp_f > self.entry):
					continue
				self.tp.append(tp_f)
				self.tp = sorted(list(set(self.tp)),
								 reverse=True)


	def get_flag(self):
		'''Checks that there's no problem of incoherence and returns the flag'''

		if all(x is not None for x in [self.sl, self.entry, self.side]):

			if self.entry > self.sl: 
				d_side = 'buy'
			elif self.entry < self.sl:
				d_side = 'sell'
			elif self.sl == self.entry :
				self.flag = 'no-data'
			
			if d_side != self.side:
				self.flag = 'no-data'

		return self.flag


	def to_dict(self):
		'''Converts obj to dict'''
		return {'time': self.time,
				'text': self.text,
				'ticker': self.ticker,
				'entry': self.entry,
				'sl': self.sl,
				'side': self.side,
				'flag': self.flag,
				'tp': self.tp}


def interpret(text: str, time: datetime, localize_tz):

	'''
	The interpreter takes in a string and parses it based on a few criterias:
	1. is there a SL pattern
	2. is there a TP pattern
	... to-do
	'''

	log = logging.getLogger()

	# istances signal obj
	sig = Signal(text, time, localize_tz)

	# goes through all the aliases to find a match in the text
	for k in aliases:

		comp = '|'.join([k, *aliases[k]]) 		# unpacking the dict
		reg = rf"(?:\b({comp})\b)"		  		# i.e. '\b(XAUUSD|gold|xau)\b'
		pair = re.compile(reg, re.I|re.M)
		
		if pair.search(text):
			sig.ticker = k
			break


	# compiling sl regex
	slRE = r'(?:sl|stops?|stop ?loss)(?:\W{1,3})(\d{1,6}\.?\d{0,5})'
	slC = re.compile(slRE, re.I|re.M)

	# compiling entry regex
	entryRE = r'(?:entry|price)(?:\W{1,3})(\d{1,6}\.?\d{0,5})'
	entryC = re.compile(entryRE, re.I|re.M)

	# compiling tp regex
	tpRE = r'(?:tp|take profits?)(?: ?\d?[^a-zA-Z0-9.]{1,3})(\d{1,6}\.?\d{1,5})'
	tpC = re.compile(tpRE, re.I|re.M)

	# compiling side regex
	sideRE = r'(?:\b(buys?!?|longs?!?|sells?!?|shorts?!?)\b)'
	sideC = re.compile(sideRE, re.I|re.M)

	# compiling partials regex
	partialsRE = r'(?:\b((?:take )?partials?|take profits?)\b)'
	partialsC = re.compile(partialsRE, re.I|re.M)

	# compiling close regex
	closeRE = r'(?:\b(closed?)\b)'
	closeC = re.compile(closeRE, re.I|re.M)

	# compiling breakeven regex
	beRE = r'(?:\b((?:stops? (?:loss )?|sl )to (?:break ?even|bep?|entry))\b)'
	beC = re.compile(beRE, re.I|re.M)


	# results
	sl_match = slC.search(text)
	entry_match = entryC.search(text)
	side_match = sideC.search(text)
	partials_match = partialsC.search(text)
	close_match = closeC.search(text)
	tp_match = tpC.findall(text)
	be_match = beC.search(text)


	try: # assigns values
		sig.sl = float(sl_match.groups()[0])
	except AttributeError:
		pass
	
	try:
		sig.side = 'buy' if any(
			w in side_match.groups()[0].lower() for w in ['buy', 'long']) else 'sell'
	except AttributeError:
		pass
	
	try:
		sig.entry = float(entry_match.groups()[0])
	except AttributeError:
		pass

	# adds tps
	sig.add_tp(tp_match)
	

	# if these are missing it's not an order
	if all(x is None for x in [sl_match, entry_match, side_match]):

		# could be a close signal
		if close_match is not None:
			sig.flag = 'close'

		elif be_match is not None:
			sig.flag = 'breakeven'

		# could be a partials signal
		elif partials_match is not None:
			sig.flag = 'partials'

		# could be a update-tp
		elif len(tp_match) > 0:
			sig.flag = 'update-tp'

		else: # it's just a text
			sig.flag = 'message'

		return sig

	# no sl, no ticker or no side, returns with 'no-data' flag
	if any(x is None for x in [sl_match, sig.ticker, side_match]):
		sig.flag = 'no-data'
		return sig

	# market execution, 'market' flag
	if entry_match is None:
		sig.flag = 'market'
		return sig

	# the only other case is limit order
	sig.flag = 'limit'
	return sig