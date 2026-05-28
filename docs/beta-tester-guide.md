# Market Bot — Guía del beta tester

Gracias por probar Market Bot. Esta guía es corta a propósito: lo importante es que entres, juegues un rato y nos cuentes qué te pareció.

## 1. Qué es Market Bot

Una herramienta de análisis de acciones pensada para el inversor argentino, con foco en CEDEARs. La idea es ayudarte a decidir qué hacer con tus posiciones (mantener, sumar, vender) comparando contra las alternativas locales: MEP, CCL, inflación y plazo fijo.

## 2. Cómo arrancar

1. Entrá a la URL que te pasamos y **creá una cuenta** (`username + password`, no mandamos mails ni verificación todavía).
2. **Definí tu perfil inversor**: horizonte de tiempo, tolerancia al riesgo y objetivo. Sin esto las recomendaciones salen genéricas.
3. **Cargá al menos una posición**. Tenés dos formas:
   - Manual: agregás ticker, cantidad y precio promedio.
   - Importar desde Balanz: bajás el extracto `.xlsx` de tu cuenta y lo subís. Si tenés cuenta en otro broker, pegá las posiciones a mano por ahora.

Con eso ya podés empezar a usarlo.

## 3. Qué probar primero

- **Analizá un ticker**: AAPL, NVDA o MELI son buenos para arrancar (datos abundantes). Mirá cómo se arma la recomendación y si las razones que da te cierran.
- **Radar de oportunidades**: ranking de qué está barato/caro según los criterios del bot. Útil para descubrir cosas que no tenías en el radar.
- **Tu portfolio vs benchmarks**: en el resumen del portfolio vas a ver cómo te fue comparado contra MEP, CCL, inflación y plazo fijo. Es la métrica que más nos importa.
- **Glosario y explicaciones**: cuando veas un término que no entendés, hacé click. Si no hay explicación o no se entiende, es un bug que queremos saber.

## 4. Qué reportar

- **Bugs**: cualquier cosa que se rompa, no cargue, o muestre datos raros. Captura ayuda mucho.
- **"Esto no me cierra"**: si la recomendación te parece equivocada o el análisis no tiene sentido para tu caso, contanos. Es el feedback más valioso.
- **UX confusa**: si no encontraste algo, si una pantalla te confundió, si pensaste que un botón hacía otra cosa.
- **Lo que te falta**: features que esperabas y no están.

No hace falta que escribas un informe, una frase alcanza. Si podés, agregá el ticker o la pantalla donde pasó.

## 5. Limitaciones conocidas

- Está corriendo en una sola instancia con auto-sleep. La primera request después de un rato sin uso puede tardar unos segundos (la app estaba "dormida").
- Es **beta**: puede haber bugs, datos desactualizados o features a medio terminar.
- Los precios y datos de mercado tienen delay (no son tiempo real).
- **No uses esto para operar con plata real todavía**. Es para evaluar la herramienta, no para tomar decisiones de inversión.
- No hay recuperación de password todavía. Si te olvidás, avisanos y la reseteamos a mano.

## 6. Contacto

- Email: _(a completar por el dueño)_
- Discord / WhatsApp: _(a completar)_

Cualquier duda, escribinos. Gracias por bancar el proyecto en esta etapa.
