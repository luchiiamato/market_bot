# UI Prototype Notes

## Interaction State Matrix

| Element | Default | Hover / Focus | Loading | Error / Empty | Selected |
| --- | --- | --- | --- | --- | --- |
| Ticker input | large calm field | visible ring and brighter border | locked while analyzing | inline message if empty | keeps active ticker pinned |
| Horizon switch | segmented control | lift and contrast shift | disabled during load | n/a | solid active pill |
| Analyze button | bold primary CTA | translate up 2px | width preserved with spinner | retry possible | n/a |
| Radar cards | editorial card grid | elevated with outline glow | skeleton shimmer | empty copy if no cards | selected card gets accent edge |
| Analysis panels | layered surface | subtle outline emphasis | shimmer overlay | “insufficient data” pattern | main verdict stays expanded |

## Motion Tokens

```css
:root {
  --motion-fast: 120ms;
  --motion-base: 220ms;
  --motion-slow: 420ms;
  --ease-standard: cubic-bezier(.2, .8, .2, 1);
  --ease-emphasized: cubic-bezier(.16, 1, .3, 1);
}
```

## Accessibility Notes

- semantic buttons for the horizon switch and radar cards
- live region for analysis status
- visible `:focus-visible` styling
- reduced motion support in CSS
- no hover-only controls

## Production Polish Checklist

- hover states implemented
- focus states implemented
- loading state avoids layout shift
- empty state present
- reduced motion covered
- selected state visible

## API Connection

- Default API base: `http://127.0.0.1:8000`
- Override with query param: `?apiBase=http://host:port`
- Rankings call `GET /rankings?cedear_only=true`
- Suggestions are restricted to CEDEAR tickers only
