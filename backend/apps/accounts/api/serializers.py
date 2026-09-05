"""Serializers for the auth endpoints (PLAN §6.1)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class MembershipStatusSerializer(serializers.Serializer):
    """The ``membership_status`` dict returned by ``members.services``."""

    status = serializers.ChoiceField(choices=["current", "expired", "none"])
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    is_lifetime = serializers.BooleanField()


class UserSerializer(serializers.ModelSerializer):
    """``user :=`` in PLAN §6.1."""

    roles = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "roles",
            "is_active",
            "membership",
            "profile_complete",
        ]
        read_only_fields = fields

    def get_roles(self, obj) -> list[str]:
        return obj.roles

    def get_membership(self, obj) -> dict:
        return MembershipStatusSerializer(obj.membership_status).data

    def get_profile_complete(self, obj) -> bool:
        profile = getattr(obj, "profile", None)
        return bool(profile and profile.is_complete)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class RoleSerializer(serializers.Serializer):
    slug = serializers.CharField()
    description = serializers.CharField()
