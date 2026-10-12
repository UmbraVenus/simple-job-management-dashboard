"""What the API accepts and what it returns.

The two input serializers repeat the rules of ``services.py`` so a bad body
gets a 400 that names the field. They declare one field each: anything else in
a body (``current_status``, ``id``, timestamps) is dropped, not written.
"""
from rest_framework import serializers

from jobs.models import Job, StatusType


class JobSerializer(serializers.ModelSerializer):
    """A job as the API returns it. Output only."""

    class Meta:
        model = Job
        fields = ["id", "name", "current_status", "created_at", "updated_at"]
        read_only_fields = fields


class JobCreateSerializer(serializers.Serializer):
    """Body of ``POST /api/jobs/``."""

    # CharField trims first, then refuses blank, over-long, NUL-containing and
    # unencodable text. A number is accepted and stored as its text.
    name = serializers.CharField(max_length=Job._meta.get_field("name").max_length)


class StatusChangeSerializer(serializers.Serializer):
    """Body of ``PATCH /api/jobs/<id>/``."""

    status_type = serializers.ChoiceField(choices=StatusType.choices)
