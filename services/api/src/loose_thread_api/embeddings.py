from dataclasses import dataclass

from openai import AsyncOpenAI

from loose_thread_api.config import Settings


@dataclass(frozen=True)
class EmbeddingOutput:
    vector: list[float]
    model: str
    usage: dict[str, int]


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required for embeddings")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())
        self._model = settings.openai_embedding_model
        self._dimensions = settings.embedding_dimensions

    async def embed(self, text: str) -> EmbeddingOutput:
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimensions,
            encoding_format="float",
        )
        if len(response.data) != 1:
            raise ValueError("embedding response did not contain exactly one vector")
        vector = response.data[0].embedding
        if len(vector) != self._dimensions:
            raise ValueError("embedding vector has an unexpected dimension")
        usage = response.usage
        return EmbeddingOutput(
            vector=vector,
            model=self._model,
            usage={
                "prompt_tokens": usage.prompt_tokens,
                "total_tokens": usage.total_tokens,
            },
        )
