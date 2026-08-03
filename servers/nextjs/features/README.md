# Feature modules

Feature packages own product-specific state, workflows, and configuration.
They may import shared UI and editor-domain modules. Shared UI must not import
feature packages; this direction is enforced by `npm run check:boundaries`.

Existing screens remain under `app/` while they are incrementally reduced to
transport/composition adapters. New presentation-chat behavior belongs in
`features/presentation-chat/` rather than the legacy `Chat.tsx` container.
