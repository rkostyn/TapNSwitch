"""Shared Jinja2Templates instance with custom filters registered."""

import os
from typing import Any
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
from starlette.responses import Response
from app import template_filters


class _AsyncTemplateResponse(Response):
    """Defers template rendering to the async ASGI __call__ so async filters work."""

    media_type = "text/html"

    def __init__(
        self,
        template: Any,
        context: dict,
        status_code: int = 200,
        headers: dict | None = None,
        background: BackgroundTask | None = None,
    ):
        self.template = template
        self.context = context
        super().__init__(
            content=b"",
            status_code=status_code,
            headers=headers,
            background=background,
        )

    async def __call__(self, scope, receive, send):
        content = await self.template.render_async(self.context)
        self.body = content.encode("utf-8")
        self.init_headers()
        await super().__call__(scope, receive, send)


class _AsyncJinja2Templates(Jinja2Templates):
    def TemplateResponse(
        self,
        *args,
        **kwargs,
    ) -> _AsyncTemplateResponse:
        # Resolve args the same way Starlette does: (name, context, ...) or keyword-only
        if args:
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", {})
        else:
            name = kwargs.pop("name")
            context = kwargs.pop("context", {})

        request = kwargs.pop("request", context.get("request"))
        status_code = kwargs.pop("status_code", 200)
        headers = kwargs.pop("headers", None)
        background = kwargs.pop("background", None)

        context.setdefault("request", request)

        template = self.get_template(name)
        return _AsyncTemplateResponse(
            template=template,
            context=context,
            status_code=status_code,
            headers=headers,
            background=background,
        )


templates = _AsyncJinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates"),
    enable_async=True,
)

templates.env.filters["datetimeformat"] = template_filters.datetimeformat
templates.env.filters["retrieve_x_latest"] = template_filters.retrieve_x_latest
templates.env.filters["find_related"] = template_filters.find_related
templates.env.filters["find_player_matches"] = template_filters.find_player_matches
