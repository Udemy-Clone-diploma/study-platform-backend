DEFAULT_TOP_REVIEWS_LIMIT = 4

# A review enters the moderator queue once at least this many distinct people
# have reported it. Multiple reports on the same review never duplicate the
# card: it stays one Review row with an annotated count and a nested reports list.
REVIEW_MODERATION_REPORT_THRESHOLD = 1