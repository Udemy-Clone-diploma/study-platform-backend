class PaymentError(Exception):
    pass


class RefundError(PaymentError):
    """A refund the platform refuses on business grounds (already refunded,
    over the refundable remainder). Views translate it to 409 and print the
    message straight into the administrator's confirmation modal."""
