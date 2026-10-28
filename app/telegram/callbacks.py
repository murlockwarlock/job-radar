from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CallbackAction:
    action: str
    value: str

    @classmethod
    def parse(cls, data: str | None) -> "CallbackAction | None":
        if not data or ":" not in data:
            return None
        action, value = data.split(":", 1)
        return cls(action=action, value=value)

    def encode(self) -> str:
        return f"{self.action}:{self.value}"


BLACKLIST_EMPLOYER_ACTION = "blacklist_employer"
