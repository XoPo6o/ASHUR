# KI.LAM — графическая спецификация (Mega Drive authentic)

## Зафиксированное направление
- Аппаратный ориентир: Sega Mega Drive / Genesis, 16-bit.
- Художественный референс: Castlevania III: Dracula's Curse — мрачная готическая читаемость, контрастные силуэты, ступенчатые контуры, ограниченные цветовые акценты. Это референс настроения и композиции, не копирование ассетов.
- Целевая сцена: ночной месопотамский базар. Исторические формы и предметы остаются оригинальными для KI.LAM.

## Рендер-контракт
- Финальный framebuffer: 320×224.
- Активный framebuffer и display canvas: 320×224. Мировая сцена: 480×336; на desktop выводится целиком масштабом 2/3, без пост-рендерного уменьшения. На mobile portrait включается приближение 1.25× и камера по путнику с вертикальным кадрированием улицы; CSS `object-fit: cover` заполняет viewport без искажения пропорций.
- Примитивы `px()` и `line()` привязываются к нативной сетке через `snapNative()` с учётом активного camera scale; offsets камеры, masonry tiles и traveler sprite снапятся к целым нативным пикселям. Сглаживание отключено.
- Цвет: 9-bit RGB-подобная палитра Mega Drive (3 бита на канал; 512 возможных цветов).
- Бюджет: четыре палитровых банка по 16 записей; запись 0 каждого банка зарезервирована. Кадр композится из отдельного background framebuffer и прозрачного sprite framebuffer. Дальний план использует bank 0, базарный средний план — bank 1, путник/спрайтовый слой — bank 2, передний план и атмосферные эффекты — bank 3; каждый банк содержит 15 видимых цветов плюс зарезервированный нулевой слот. После композиции кадр содержит не более 60 цветов.
- Тайлы: 8×8 px; нативный tile atlas реализован в `intro.js`: 4 варианта мощения и 4 варианта кирпичной кладки. Мощение собрано в 40×25 tilemap, кирпичная кладка используется в стенах зиккурата, террасах висячих садов и фасадах дальнего города; ряды перевязаны со смещением. Оконные проёмы дальнего города строятся ступенчатыми арками из пиксельных прямоугольников — Canvas vector arcs не используются.
- Спрайты: путник вынесен в отдельный 4-кадровый sheet 16×24 native px (64×24 общий атлас); кадры idle/left/passing/right выбираются по фазе шага. Поверх базового атласа работает character craft pass: окантовка капюшона, тень лица и борода, вышитая накидка, пояс с бронзовой пряжкой, швы сумки, свёрнутый плед и блики сапог. Торговцы получили разные читаемые роли — продавец специй, торговец лампами, носильщик корзин и страж — с индивидуальными силуэтными деталями. Внутри логического framebuffer спрайты выводятся nearest-neighbor без сглаживания на отдельном прозрачном sprite framebuffer; traveler layer использует bank 2, прозрачные пиксели сохраняют alpha=0.
- Слои: программный композитор разделяет background framebuffer и прозрачный sprite framebuffer. В background framebuffer bank 0 назначен дальнему небу/архитектуре, bank 1 — базарному среднему плану, bank 3 — переднему плану и атмосферным эффектам; отдельный sprite framebuffer использует bank 2. Это программная имитация структуры двух background planes + sprite plane, не аппаратная эмуляция Mega Drive.

## Анимация
- Персонаж: целевой темп 12 кадров/с; ступенчатые позы и читаемый цикл ходьбы.
- Вторичные элементы: 6–8 кадров/с; мерцание фонарей без альфа-градиентов.
- В рендере интро удалены Canvas linear/radial gradients и globalAlpha: небо строится ступенчатыми полосами, фонари — пиксельными пятнами света, тени — жёсткими ступенями. Blur, bloom, film grain и CSS-фильтры не используются.
- Камерный shake — только целыми пикселями.

## Арт-дирекшн
- Контрастные тёмные силуэты и ограниченные локальные источники света, как в Castlevania III.
- Архитектура: крупные ступенчатые формы, арки и кирпичные тайлы; отдельный detail pass добавляет рельефные пояса зиккурата, розетки, храмовые капители, оконные перемычки, терракотовые кашпо, водостоки и резьбу ламассу.
- Рынок: отдельный foreground craft pass детализирует вышивку ковров, керамические метки, плетение корзин, швы навесов, кисти и специи на прилавке; декор рисуется жёсткими пиксельными пятнами и остаётся в общей 12 FPS-сетке.
- Цветовые акценты: охра/терракота для камня и тканей; холодные сине-зелёные тени; янтарный свет фонарей.
- Персонаж должен читаться на фоне рынка по силуэту, а не за счёт градиентной подсветки.
- Логотип KI.LAM сохраняет утверждённую квадратную сетку 3×2 и отдельную точку в центре своей ячейки.

## Приёмка
1. Canvas framebuffer строго 320×224.
2. Выходной кадр без bilinear smoothing и без субпиксельного смещения.
3. Не более 60 видимых цветов на кадр в текущем общем палитровом режиме.
4. Пол игрового пространства собирается из повторно используемых 8×8 native tiles; нет градиентной заливки пола.
5. 12 FPS cap для основной анимации.
6. Desktop: полный 320×224 кадр; mobile portrait и landscape: camera-follow кадрирование на путнике с заполнением viewport без растяжения пропорций.
7. Skip по тапу/клику, Escape, Space, Enter; reduced-motion показывает финальный экран.
8. Следующий production-этап: художественная полировка наблюдателей, микродвижений окружения и ручная визуальная приёмка на реальном Android-устройстве.

## Camera, observers and title sequence

- Mobile portrait and landscape cameras follow the traveler in world coordinates; portrait uses a 1.25× zoom, landscape a 1.125× zoom, and both shift the vertical framing toward the street while preserving the 320×224 framebuffer and nearest-neighbor pixel rendering. The 480×336 world floor fills the full framebuffer, with no unused lower strip.
- Four separate observer silhouettes stand around the central market lane. On the fall beat they stop, turn toward the traveler and raise/point an arm.
- Opening text appears first, fades out completely, cuneiform appears alone, then fades before the KI.LAM mark.
- GitHub Pages deploy workflow is triggered by pushes to `game-dev`; `main` remains untouched.

## Bazaar character animation

- Spice seller: 12fps scoop, lift, pour and scale-settle loop.
- Lamp merchant: 12fps lamp lift and flame-check loop.
- Porter: 12fps shoulder-load shift loop.
- Gate watcher: 12fps staff tap and return-to-guard loop.
- Motion uses discrete native-pixel poses; no smooth tweening.
