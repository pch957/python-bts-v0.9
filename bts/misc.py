# -*- coding: utf-8 -*-
import re


def _to_fixed_point(match):
    """Return the fixed point form of the matched number.

    Parameters:
        match is a MatchObject that matches exp_regex or similar.

    If you wish to make match using your own regex, keep the following in mind:
        group 1 should be the coefficient
        group 3 should be the sign
        group 4 should be the exponent
    """
    sign = -1 if match.group(3) == "-" else 1
    coefficient = float(match.group(1))
    exponent = sign * float(match.group(4))
    if exponent <= 0:
        format_str = "%." + "%d" % (-exponent + len(match.group(1)) - 2) + "f"
    else:
        format_str = "%.1f"
    return format_str % (coefficient * 10 ** exponent)


def to_fixed_point(string):
    exp_regex = re.compile(r"(\d+(\.\d+)?)[Ee](\+|-)(\d+)")
    return exp_regex.sub(_to_fixed_point, str(string))


def trim_float_precision(number, precision):
    format_str = "%." + "%d" % (len(str(int(precision))) - 1) + "f"
    return format_str % number


def get_median(prices):
    lenth = len(prices)
    if lenth == 0:
        return None
    _index = int(lenth / 2)
    if lenth % 2 == 0:
        median_price = float((prices[_index - 1] + prices[_index])) / 2
    else:
        median_price = prices[_index]
    return median_price
