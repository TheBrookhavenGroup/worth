from worth.utils import is_not_near_zero


def pcnt_change(initial, final=None, delta=None):
    if is_not_near_zero(initial):
        if delta is None:
            delta = final - initial
        return delta / initial

    return 0
