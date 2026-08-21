import asyncio
from datetime import datetime

from tortoise import fields, models

from app.settings import settings


class BaseModel(models.Model):
    id = fields.BigIntField(pk=True, index=True)

    SENSITIVE_FIELDS = frozenset(
        {
            "password",
            "api_config",
            "totp_secret",
            "recovery_question",
            "recovery_answer_hash",
            "recovery_fail_count",
            "recovery_locked_until",
        }
    )

    async def to_dict(self, m2m: bool = False, exclude_fields: list[str] | None = None):
        blocked = set(exclude_fields or []) | self.SENSITIVE_FIELDS

        d = {}
        for field in self._meta.db_fields:
            if field not in blocked:
                value = getattr(self, field)
                if isinstance(value, datetime):
                    value = value.strftime(settings.DATETIME_FORMAT)
                d[field] = value

        if m2m:
            tasks = [
                self.__fetch_m2m_field(field, blocked)
                for field in self._meta.m2m_fields
                if field not in blocked
            ]
            results = await asyncio.gather(*tasks)
            for field, values in results:
                d[field] = values

        return d

    async def __fetch_m2m_field(self, field, exclude_fields):
        values = await getattr(self, field).all().values()
        formatted_values = []
        blocked = set(exclude_fields or []) | self.SENSITIVE_FIELDS

        for value in values:
            formatted_value = {}
            for k, v in value.items():
                if k not in blocked:
                    if isinstance(v, datetime):
                        formatted_value[k] = v.strftime(settings.DATETIME_FORMAT)
                    else:
                        formatted_value[k] = v
            formatted_values.append(formatted_value)

        return field, formatted_values

    class Meta:
        abstract = True


class UUIDModel:
    uuid = fields.UUIDField(unique=True, pk=False, index=True)


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True, index=True)
    updated_at = fields.DatetimeField(auto_now=True, index=True)
