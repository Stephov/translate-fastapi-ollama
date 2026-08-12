from dataclasses import asdict, dataclass
import re


@dataclass
class SmsTemplate:
    n: int | None
    subject: str
    trans_type: str
    latarm: str
    arm: str
    eng: str
    rus: str
    reverse_indicator: str | None = None
    resp_code: str | None = None

    @staticmethod
    def _strip_placeholders(text: str) -> str:
        # Placeholders are shared across SMS templates and hurt similarity ranking.
        without = re.sub(r"<[^>]+>", " ", text)
        return " ".join(without.split()).strip()

    def search_text(self) -> str:
        """Text used for embedding / similarity search."""
        return " | ".join(
            part
            for part in (
                self.subject,
                self.trans_type,
                self._strip_placeholders(self.latarm),
                self._strip_placeholders(self.eng),
                self._strip_placeholders(self.arm),
                self._strip_placeholders(self.rus),
            )
            if part
        )

    def to_prompt_block(self) -> str:
        return (
            f"subject: {self.subject}\n"
            f"trans_type: {self.trans_type}\n"
            f"latarm: {self.latarm}\n"
            f"arm: {self.arm}\n"
            f"eng: {self.eng}\n"
            f"rus: {self.rus}"
        )

    def to_dict(self) -> dict:
        return asdict(self)
