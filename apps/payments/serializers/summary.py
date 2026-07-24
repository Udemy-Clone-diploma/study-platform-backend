from rest_framework import serializers


class PaymentSummaryCurrencySerializer(serializers.Serializer):
    """Totals for one currency. Amounts never sum across currencies."""

    currency = serializers.CharField()
    gross_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    refunded_amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    pending_amount = serializers.DecimalField(max_digits=14, decimal_places=2)


class PaymentSummaryCountsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    processing = serializers.IntegerField()
    succeeded = serializers.IntegerField()
    failed = serializers.IntegerField()
    canceled = serializers.IntegerField()
    refunded = serializers.IntegerField()
    # Not a status: these payments are still `succeeded`, with part of the
    # charge returned. `refunded` above counts fully refunded payments only.
    partially_refunded = serializers.IntegerField()


class PaymentSummaryPreviousSerializer(serializers.Serializer):
    """The equally long window immediately before the requested one."""

    date_from = serializers.DateField()
    date_to = serializers.DateField()
    by_currency = PaymentSummaryCurrencySerializer(many=True)
    counts = PaymentSummaryCountsSerializer()


class PaymentSummarySerializer(serializers.Serializer):
    by_currency = PaymentSummaryCurrencySerializer(many=True)
    counts = PaymentSummaryCountsSerializer()
    # Null unless both date_from and date_to were supplied: without a window
    # there is nothing to shift back by.
    previous = PaymentSummaryPreviousSerializer(allow_null=True)


class PaymentTimeseriesPointSerializer(serializers.Serializer):
    period = serializers.DateField()
    currency = serializers.CharField()
    gross_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)


class PaymentCategoryRevenueSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(allow_null=True)
    category = serializers.CharField(allow_null=True)
    slug = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    gross_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
