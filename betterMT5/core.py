from datetime import datetime, timedelta
import pymt5adapter as mt5
from math import ceil
import pandas as pd
import time
import pytz

TIMEFRAME = mt5.TIMEFRAME

class UnexpectedValueError(ValueError):
    def __init__(self, expected, actual, rates=None):
        self.diff = expected-actual
        self.message = f'{expected=} but got {actual=}, diff={self.diff}'
        self.rates = rates
        super().__init__(self.message)


def are_datetimes_eq(date1, date2, window=1):
    '''Since datetimes don't support the __eq__ operator per se, this function
    will determine if two dates are in the same windowed range (in seconds), and 
    return True if they are (which basically means that they are that much close to e.o.)'''
    return abs((date1 - date2).total_seconds()) <= window


def get_current_tz_offset():
    '''Function that calculated current tz offset with broker server based on the difference
    between the last candle time and the current utc time.

    TO-DO: allow function to work on weekends (currently it will just return last friday's candle
    TO-DO: allow function to work even if "EURUSD" isn't supported by broker'''

    last_candle = mt5.copy_rates_from_pos('EURUSD',
                                          TIMEFRAME.M1,
                                          start_pos=0,
                                          count=1)
    last_candle_time = datetime.fromtimestamp(last_candle[0][0])
    reference = datetime.utcnow().replace(second=0, microsecond=0)
    offset = (last_candle_time - reference).total_seconds() / 3600

    return offset


def to_seconds(timeframe: TIMEFRAME):
    return mt5.period_seconds(timeframe)


def to_timedelta(timeframe: TIMEFRAME):
    return timedelta(seconds=to_seconds(timeframe))


def connected(**kwargs):
    return mt5.connected(**kwargs)


def localized_date_to_mt5(date):
    """Converts a timezone-aware date to the format expected by mt5.

    This function was written with GMT+2/+3 offset in mind. If the
    broker tz is not one of these, it might produce unexpected results"""

    # timezones
    nytz = pytz.timezone("US/Eastern")
    gmt2 = pytz.timezone("Etc/GMT-2")
    gmt3 = pytz.timezone("Etc/GMT-3")

    # convert to nytz
    nydate = date.astimezone(nytz)

    # if date is a Timestamp object, convert to datetime
    if isinstance(date, pd.Timestamp):
        date = date.to_pydatetime()

    # check if it's dst, if it is, assign gmt3
    if bool(nydate.dst()):
        return date.astimezone(gmt3).replace(tzinfo=pytz.UTC)
    else:
        return date.astimezone(gmt2).replace(tzinfo=pytz.UTC)


def mt5_date_to_utc(data):
    """Takes a timezone-naive datetime obj as input (or dataframe, as this was
    designed to convert the mt5 rates output by the different copy_rates functions
    from mt5) and localizes it based on whether NY is in DST or not.

    This function was written with GMT+2/+3 offset in mind. If the
    broker tz is not one of these, it might produce unexpected results"""

    nytz = pytz.timezone("US/Eastern")

    # this is REALLY counterintuitive (would expect GMT+2/+3) but here's the explanation:
    # https://stackoverflow.com/questions/54842491/printing-datetime-as-pytz-timezoneetc-gmt-5-yields-incorrect-result
    gmt2 = pytz.timezone("Etc/GMT-2")
    gmt3 = pytz.timezone("Etc/GMT-3")

    try:

        date = data

        # localize mt5 date to gmt2 (might be wrong, we don't know yet)
        gmt2date = gmt2.localize(date)
        gmt3date = gmt3.localize(date)

        # turn it into ny time
        nydate = gmt2date.astimezone(nytz)

        # check if it's dst, if it is, gmt2 is wrong, return utc
        if bool(nydate.dst()):
            return gmt3date.astimezone(pytz.utc)

        # if it's not, localize to gmt2 and then return utc
        else:
            return gmt2date.astimezone(pytz.utc)

    except AttributeError:

        # iterates over bar/ticks and adjusts the dates
        df = pd.DataFrame(data)
        # if df is empty, return it
        if df.shape[0] == 0:
            return df
        # convert time in seconds/ms into the datetime format
        df["time"] = pd.to_datetime(df["time"], unit="s")
        if "time_msc" in df.columns:
            df["time"] = pd.to_datetime(df["time_msc"], unit="ms")
        # applies itself to column
        df["time"] = df["time"].map(lambda d: mt5_date_to_utc(d))

        return df


def is_datetime_exactly_at_start_of_timeframe_range(time: datetime,
                                                    timeframe: TIMEFRAME):
    """This is used to check if a date is exactly at the start of the range defined by
    the timeframe, for example: 15:05 is exactly at the start of a TIMEFRAME.M5 candle,
    while 15:06 isn't. The reason why this is important is tha mt5 will return candles
    starting from exactly the date requested or, if the date isn't exactly at the start
    of the range, the next available candle. The problem is that if we want to know what
    happened at 15:06, we need the 15:05 candle, and therefore we need to account for the offset.

    Problem is, if we add an offset of exactly the timeframe timedelta (ex: 15:06 - 5 minutes
    would be 15:01, which will return the 15:05 candle, which will contain information about
    what happened at 15:06), we get unintented behaviour when our requested datetime is, for
    example, 15:05. Why? Because the offset will make it 15:00, and mt5 will return candles
    starting from 15:00, which we don't want, as it is one candle too early (as the 15:05
    candle already contains info about what happened at 15:05). So, in order to fix this, we
    need to understand whether a date is exactly at the start of the timeframe range or not."""
    if time.timestamp() % to_seconds(timeframe) == 0:
        return True
    return False


class Symbol:
    """Symbol object: will have data from symbol_info and get_rates method"""

    all = list()
    allowed_symbols = None

    def __init__(self, name: str):

        # Initializes the Symbol allowed symbol dict
        if Symbol.allowed_symbols is None:
            try:
                Symbol.allowed_symbols = {v.name: v for v in mt5.symbols_get()}
            except TypeError:
                raise ValueError(
                "You must initiate Symbol inside a mt5.connected() context manager"
            )

        self.name = name
        self.info = Symbol.allowed_symbols.get(name, None)
        if self.info is None:
            raise ValueError(
                "You must initiate Symbol inside a mt5.connected() context manager"
            )
        # Appends to Symbol.all list
        if self._name not in [s.name for s in Symbol.all]:
            Symbol.all.append(self)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if value not in Symbol.allowed_symbols:
            raise ValueError(f'{value=} is not supported by this broker')
        self._name = value

    @staticmethod
    def flush():
        Symbol.all = []
        Symbol.allowed_symbols = None

    def get_rates_from_pos(self, timeframe: TIMEFRAME, start_pos=0, count=1):
        for n in range(10):

            rates = mt5.copy_rates_from_pos(self.name, timeframe, start_pos,
                                            count)

            # makes sure it's actually processed
            if len(rates) > 0:
                break
            time.sleep(0.1)

        rates = mt5_date_to_utc(rates)

        if len(rates) != count:
            raise UnexpectedValueError(count, len(rates), rates)

        return rates

    def get_rates_from(self,
                       timeframe: TIMEFRAME,
                       datetime_from: datetime,
                       count=1):

        datetime_from_adj = localized_date_to_mt5(datetime_from)

        for n in range(10):
            rates = mt5.copy_rates_from(self.name, timeframe,
                                        datetime_from_adj.timestamp(), count)
            # makes sure it's actually processed
            if len(rates) > 0:
                break
            time.sleep(0.1)

        rates = mt5_date_to_utc(rates)  # adjusts rates

        # Checks that the datetime_from returned has the correct date
        if not are_datetimes_eq(rates['time'].iloc[-1],
                                datetime_from,
                                window=to_seconds(timeframe)):
            raise UnexpectedValueError(datetime_from, rates['time'].iloc[-1])

        # Checks that the expected datetime_to is correct
        exp_datetime_to = datetime_from - to_timedelta(timeframe) * (count - 1)
        if not are_datetimes_eq(rates['time'].iloc[0],
                                exp_datetime_to,
                                window=to_seconds(timeframe)):
            raise UnexpectedValueError(exp_datetime_to, rates['time'].iloc[0])

        return rates

    def get_rates_range(self,
                        timeframe: TIMEFRAME,
                        datetime_from: datetime,
                        datetime_to: datetime,
                        include_first: bool = True,
                        include_last: bool = True):

        datetime_from_adj = localized_date_to_mt5(datetime_from)
        datetime_to_adj = localized_date_to_mt5(datetime_to)
        offset = to_timedelta(timeframe)

        if is_datetime_exactly_at_start_of_timeframe_range(
                datetime_from, timeframe):
            if not include_first:
                # if datetime is at start of the range and we don't
                # want the first candle we move the time up
                datetime_from_adj += offset
        else:
            if include_first:
                # if datetime is NOT at start of the range and we DO
                # want the first candle we move the time back
                datetime_from_adj -= offset

        if not include_last:
            # if we don't want the last candle, we can just
            # move time back, as the default behaviour of mt5
            # is inclusive anyway
            datetime_to_adj -= offset

        for n in range(10):
            rates = mt5.copy_rates_range(self.name, timeframe,
                                         datetime_from_adj.timestamp(),
                                         datetime_to_adj.timestamp())
            # makes sure the request is actually processed
            if len(rates) > 0:
                break
            time.sleep(0.1)

        rates = mt5_date_to_utc(rates)  # adjusts rates

        # Checks that the datetime_from returned has the correct date
        if not are_datetimes_eq(rates['time'].iloc[0],
                                datetime_from,
                                window=to_seconds(timeframe)):
            raise UnexpectedValueError(datetime_from, rates['time'].iloc[0])

        # Checks that the datetime_to returned has the correct date
        if not are_datetimes_eq(rates['time'].iloc[-1],
                                datetime_to,
                                window=to_seconds(timeframe)):
            raise UnexpectedValueError(datetime_to, rates['time'].iloc[-1])

        # Checks that the rates returned match the expected size of the request
        seconds_range = abs((datetime_to - datetime_from).total_seconds())
        seconds_tf = to_seconds(timeframe)
        exp_candles = int(
            ceil(seconds_range / seconds_tf) # it will always be upper bound
            + include_first # +1 if first candle is included
            + include_last - 1)  # -1 if last candle is not included

        if abs(len(rates) - exp_candles) > 0:
            raise UnexpectedValueError(exp_candles, len(rates), rates)

        return rates

    def history(self,
                timeframe: TIMEFRAME,
                datetime_from: datetime = None,
                datetime_to: datetime = None,
                start_pos: int = 0,  # this way it can pass through
                count: int = None,
                include_first: bool = True,
                include_last: bool = True):
        """Interface: returns the correct result based on the provided args.
        Leaves the freedom to choose arbitrarily what kind of request you want to make to mt5"""
        if datetime_from is not None:

            if datetime_to is not None:
                return self.get_rates_range(timeframe,
                                            datetime_from=datetime_from,
                                            datetime_to=datetime_to,
                                            include_first=include_first,
                                            include_last=include_last)

            if count is not None:
                return self.get_rates_from(timeframe,
                                           datetime_from=datetime_from,
                                           count=count)

        if count is not None:
            return self.get_rates_from_pos(timeframe,
                                           start_pos=start_pos,
                                           count=count)

        # if nothing is valid it means that the wrong args have been provided
        raise AttributeError(
            "You must pass at least one argument besides start_pos")

    def get_ticks():
        raise NotImplementedError


def main():

    with mt5.connected() as conn:
        print(f'{get_current_tz_offset()=}')

        s = Symbol("GBPJPY")
        print(f"{s.info.ask=}")
        t_from = pytz.timezone("Europe/Rome").localize(
            datetime(2021, 1, 6, 11, 24))
        t_to = t_from + timedelta(hours=10, minutes=3)
        timeframe = TIMEFRAME.M5
        
        hist = s.history(timeframe, datetime_from=t_from, datetime_to=t_to)
        print(f'{timeframe=}\n{str(t_from)=}\n{str(t_to)=}\n{hist}')

        hist2 = s.get_rates_from_pos(mt5.TIMEFRAME.M1)
        print(hist2)


if __name__ == "__main__":
    main()
