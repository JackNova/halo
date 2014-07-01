
def eta(total, rate, start=0, biggest_unit_only=False, min_seconds=1):
    assert start < total
    assert rate >= 0
    try:
        seconds = (total - start) / rate
    except ZeroDivisionError:
        return "infinity (will take forever as the rate is 0)"

    if seconds < min_seconds:
        seconds = min_seconds

    # TODO: allow rounding option

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    magnitudes = [
        (days, 'day%s' % ('s'[days==1:])),
        (hours, 'hour%s' % ('s'[hours==1:])),
        (minutes, 'minute%s' % ('s'[minutes==1:])),
        (seconds, 'second%s' % ('s'[seconds==1:])),
    ]

    magnitudes_str = ("{n} {magnitude}".format(n=int(amount), magnitude=unit)
                      for amount, unit in magnitudes if amount)
    eta_str = ", ".join(magnitudes_str)

    if biggest_unit_only:
        eta_str = eta_str.split(', ')[0]

    return eta_str
