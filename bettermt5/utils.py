import subprocess
import os
import platform


def are_datetimes_eq(date1, date2, window=1):
    """Since datetimes don't support the __eq__ operator per se, this function
    will determine if two dates are in the same windowed range (in seconds), and
    return True if they are (which basically means that they are that much close to e.o.)"""
    return abs((date1 - date2).total_seconds()) <= window


def get_current_tz_offset():
    """Function that calculated current tz offset with broker server based on the difference
    between the last candle time and the current utc time.

    TO-DO: allow function to work on weekends (currently it will just return last friday's candle
    TO-DO: allow function to work even if "EURUSD" isn't supported by broker"""

    last_candle = mt5.copy_rates_from_pos("EURUSD", TIMEFRAME.M1, start_pos=0, count=1)
    last_candle_time = datetime.fromtimestamp(last_candle[0][0])
    reference = datetime.utcnow().replace(second=0, microsecond=0)
    offset = (last_candle_time - reference).total_seconds() / 3600

    return offset


def to_seconds(timeframe: TIMEFRAME):
    return mt5.period_seconds(timeframe)


def to_timedelta(timeframe: TIMEFRAME):
    return timedelta(seconds=to_seconds(timeframe))


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


def is_datetime_exactly_at_start_of_timeframe_range(
    time: datetime, timeframe: TIMEFRAME
):
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


def main():
    pass


if __name__ == "__main__":
    main()
