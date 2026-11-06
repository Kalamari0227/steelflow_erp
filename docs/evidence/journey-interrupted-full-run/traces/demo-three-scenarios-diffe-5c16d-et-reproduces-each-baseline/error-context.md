# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: demo.spec.ts >> three scenarios differ at the same tick and reset reproduces each baseline
- Location: tests/demo.spec.ts:106:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: page.waitForResponse: Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=f2e3]:
  - link "Skip to operations" [ref=f2e4] [cursor=pointer]:
    - /url: "#main-content"
  - navigation "Main navigation" [ref=f2e5]:
    - link "SteelFlow home" [ref=f2e6] [cursor=pointer]:
      - /url: "#main-content"
    - button "Operations overview" [ref=f2e10] [cursor=pointer]
    - button "Inventory view" [ref=f2e16] [cursor=pointer]
    - button "Open orders" [ref=f2e27] [cursor=pointer]
    - button "Open shipments" [ref=f2e31] [cursor=pointer]
    - button "Open event history" [ref=f2e36] [cursor=pointer]
    - generic [ref=f2e39]:
      - button "Open demo guide" [ref=f2e40] [cursor=pointer]
      - generic "Local demo operator" [ref=f2e44]: SF
  - generic [ref=f2e45]:
    - banner [ref=f2e46]:
      - generic [ref=f2e47]:
        - text: SteelFlow
        - generic [ref=f2e48]: 3D
        - generic [ref=f2e50]: Operations twin
      - generic [ref=f2e53]:
        - generic [ref=f2e54]: Synthetic environment
        - generic [ref=f2e56]: LOCAL / V0.1
    - main [ref=f2e57]:
      - navigation "워크스페이스 선택" [ref=f2e58]:
        - button "물류 오버뷰" [pressed] [ref=f2e59] [cursor=pointer]
        - button "생산 공정" [ref=f2e65] [cursor=pointer]
        - button "제품 제조공정" [ref=f2e68] [cursor=pointer]
      - generic [ref=f2e73]:
        - generic [ref=f2e74]:
          - generic [ref=f2e75]: Workspace Overview
          - heading "Operations overview" [level=1] [ref=f2e78]
          - paragraph [ref=f2e80]: Your steel supply chain. One connected view.
        - generic [ref=f2e81]:
          - button "Demo guide" [ref=f2e82] [cursor=pointer]
          - generic [ref=f2e89]:
            - text: 30 OCT 2026
            - generic [ref=f2e90]: SIMULATION DATE · UTC
      - region "Operational KPIs" [ref=f2e91]:
        - generic [ref=f2e92]:
          - generic [ref=f2e93]: Active orders
          - generic [ref=f2e105]:
            - text: "6"
            - generic [ref=f2e106]: / 6
          - generic [ref=f2e107]: 0 delivered orders
          - generic "Production completion by lot" [ref=f2e109]:
            - 'generic "LOT-1001: 0 of 48 t" [ref=f2e110]'
            - 'generic "LOT-1002: 50 of 50 t" [ref=f2e111]'
            - 'generic "LOT-1003: 52 of 52 t" [ref=f2e112]'
            - 'generic "LOT-1004: 54 of 54 t" [ref=f2e113]'
            - 'generic "LOT-1005: 56 of 56 t" [ref=f2e114]'
            - 'generic "LOT-1006: 58 of 58 t" [ref=f2e115]'
        - generic [ref=f2e116]:
          - generic [ref=f2e117]: Production output
          - generic [ref=f2e121]: 270t
          - generic [ref=f2e122]: of 318 t planned
        - generic [ref=f2e126]:
          - generic [ref=f2e127]: In transit
          - generic [ref=f2e133]: 168t
          - generic [ref=f2e134]: 0 t delivered
        - generic [ref=f2e147]:
          - generic [ref=f2e148]: On-time outlook
          - generic [ref=f2e153]: 100%
          - generic [ref=f2e154]: All orders on schedule
      - generic [ref=f2e161]:
        - region "Digital twin workspace" [ref=f2e162]:
          - generic [ref=f2e163]:
            - generic [ref=f2e164]:
              - heading "Production & logistics twin" [level=2] [ref=f2e169]
              - generic [ref=f2e170]: SITE 01
            - generic [ref=f2e171]:
              - button "3D twin" [pressed] [ref=f2e172] [cursor=pointer]
              - button "2D inventory" [ref=f2e176] [cursor=pointer]
          - generic [ref=f2e178]:
            - generic [ref=f2e179]: Connected to local engine
            - generic [ref=f2e182]:
              - generic [ref=f2e183]: SCENARIO
              - combobox "Scenario" [ref=f2e184]:
                - option "Normal flow"
                - option "Production delay"
                - option "Recovery plan" [selected]
          - generic [ref=f2e185]:
            - generic [ref=f2e186]:
              - generic:
                - generic:
                  - button "Select location Customer delivery" [ref=f2e187] [cursor=pointer]: Customer delivery
                  - button "Select location Truck dispatch" [ref=f2e188] [cursor=pointer]: Truck dispatch
                  - button "Select location Hot rolling · Line A" [ref=f2e189] [cursor=pointer]: Hot rolling · Line A
                  - button "Select location Finishing · Line B" [ref=f2e190] [cursor=pointer]: Finishing · Line B
                  - button "Select location Harbor terminal" [ref=f2e191] [cursor=pointer]: Harbor terminal
                  - button "Select location Coastal shipping lane" [ref=f2e192] [cursor=pointer]: Coastal shipping lane
                  - button "Select location Coil yard" [ref=f2e193] [cursor=pointer]: Coil yard
                  - generic: C-1001 · 12 t
              - generic "Interactive synthetic steel factory. Drag to orbit, scroll to zoom, select coils for details. Use inventory table for keyboard access." [ref=f2e194]
            - generic [ref=f2e197]:
              - button "Reset camera" [ref=f2e198] [cursor=pointer]
              - button "Show zone labels" [pressed] [ref=f2e205] [cursor=pointer]
              - button "Expand twin" [ref=f2e209] [cursor=pointer]
            - generic: "N"
            - generic:
              - generic: Drag to orbit
              - text: Scroll to zoomClick to inspect
            - generic: SCHEMATIC
          - generic [ref=f2e215]:
            - generic [ref=f2e216]: Production
            - generic [ref=f2e218]: Coil yard
            - generic [ref=f2e220]: Dispatch
            - generic [ref=f2e222]: Port & shipment
            - generic [ref=f2e224]: 24 tracked coils
          - generic [ref=f2e225]:
            - button "Play simulation" [ref=f2e226] [cursor=pointer]:
              - generic [ref=f2e229]: Play
            - button "Advance one step" [ref=f2e230] [cursor=pointer]
            - button "Reset simulation" [ref=f2e233] [cursor=pointer]
            - generic [ref=f2e238]:
              - generic [ref=f2e239]: Simulation speed
              - combobox "Simulation speed" [ref=f2e240]:
                - option "1× speed" [selected]
                - option "2× speed"
                - option "4× speed"
            - generic [ref=f2e241]:
              - generic [ref=f2e242]:
                - generic [ref=f2e243]: 09:00 UTC
                - generic [ref=f2e244]: Step 2 / 24
              - progressbar "Simulation progress" [ref=f2e245]
            - generic [ref=f2e247]: Paused
        - complementary "Object inspector" [ref=f2e249]:
          - generic [ref=f2e250]:
            - generic [ref=f2e251]: coil inspector
            - button "Clear selection" [ref=f2e252] [cursor=pointer]
          - generic [ref=f2e256]:
            - generic [ref=f2e259]: STEEL COIL / SPHC
            - generic [ref=f2e260]: +
          - generic [ref=f2e261]:
            - generic [ref=f2e262]:
              - heading "C-1001" [level=2] [ref=f2e263]
              - paragraph [ref=f2e264]: Steel coil · SPHC
            - generic [ref=f2e265]: Producing
          - generic [ref=f2e267]:
            - generic [ref=f2e268]:
              - generic [ref=f2e269]: Weight
              - strong [ref=f2e270]: 12 t
            - generic [ref=f2e271]:
              - generic [ref=f2e272]: Width
              - strong [ref=f2e273]: 1250 mm
            - generic [ref=f2e274]:
              - generic [ref=f2e275]: Gauge
              - strong [ref=f2e276]: 2.5 mm
          - generic [ref=f2e277]:
            - generic [ref=f2e278]:
              - term [ref=f2e279]: Customer
              - definition [ref=f2e280]: Han River Fabrication
            - generic [ref=f2e281]:
              - term [ref=f2e282]: Linked order
              - definition [ref=f2e283]:
                - button "O-1001" [ref=f2e284] [cursor=pointer]
            - generic [ref=f2e288]:
              - term [ref=f2e289]: Production lot
              - definition [ref=f2e290]:
                - button "LOT-1001" [ref=f2e291] [cursor=pointer]
            - generic [ref=f2e295]:
              - term [ref=f2e296]: Current location
              - definition [ref=f2e297]:
                - button "Finishing · Line B" [ref=f2e298] [cursor=pointer]
            - generic [ref=f2e302]:
              - term [ref=f2e303]: Shipment
              - definition [ref=f2e304]:
                - button "SH-1001" [ref=f2e305] [cursor=pointer]
            - generic [ref=f2e309]:
              - term [ref=f2e310]: Due date
              - definition [ref=f2e311]: 30 Oct · 16:00 UTC
          - generic [ref=f2e312]:
            - strong [ref=f2e313]: Recovery applied
            - paragraph [ref=f2e314]: Projected arrival 2026-10-30T16:00:00Z; due 2026-10-30T16:00:00Z; lateness 0h. Line A outage adds 3h against 1h delivery slack. Line B and priority dispatch recover 2h.
            - text: delay_hours = max(0, (shipment.eta - order.due_at) / 1 hour)
          - generic [ref=f2e315]: Authoritative backend snapshot · 09:00 UTC
      - region "Deterministic recovery insights" [ref=f2e317]:
        - generic [ref=f2e322]:
          - generic [ref=f2e323]:
            - strong [ref=f2e324]: Recovery plan in effect
            - generic [ref=f2e325]: RULE-BASED INSIGHT
          - generic [ref=f2e326]:
            - generic [ref=f2e327]:
              - paragraph [ref=f2e328]:
                - button "O-1001" [ref=f2e329] [cursor=pointer]
                - text: · Projected arrival 2026-10-30T16:00:00Z; due 2026-10-30T16:00:00Z; lateness 0h. Line A outage adds 3h against 1h delivery slack. Line B and priority dispatch recover 2h.
              - paragraph [ref=f2e330]: Monitor the applied Line B and priority dispatch plan.
              - generic [ref=f2e331]: delay_hours = max(0, (shipment.eta - order.due_at) / 1 hour) · Delay 0h · Recovered 2h
            - generic [ref=f2e332]:
              - paragraph [ref=f2e333]:
                - button "O-1002" [ref=f2e334] [cursor=pointer]
                - text: · Projected arrival 2026-10-30T15:00:00Z; due 2026-10-30T15:00:00Z; lateness 0h. Line A outage adds 3h against 1h delivery slack. Line B and priority dispatch recover 2h.
              - paragraph [ref=f2e335]: Monitor the applied Line B and priority dispatch plan.
              - generic [ref=f2e336]: delay_hours = max(0, (shipment.eta - order.due_at) / 1 hour) · Delay 0h · Recovered 2h
        - generic [ref=f2e337]: Local rules · no AI required
      - region "Operations records" [ref=f2e339]:
        - generic [ref=f2e340]:
          - generic "Record views" [ref=f2e341]:
            - button "Orders 6" [pressed] [ref=f2e342] [cursor=pointer]:
              - text: Orders
              - generic [ref=f2e343]: "6"
            - button "Shipments 6" [ref=f2e344] [cursor=pointer]:
              - text: Shipments
              - generic [ref=f2e345]: "6"
            - button "Event history 49" [ref=f2e346] [cursor=pointer]:
              - text: Event history
              - generic [ref=f2e347]: "49"
          - generic [ref=f2e348]:
            - textbox "Search orders" [ref=f2e352]:
              - /placeholder: Search orders, customers, grades…
            - generic [ref=f2e353]: ⌕
        - region "Customer orders" [ref=f2e354]:
          - table [ref=f2e355]:
            - caption [ref=f2e356]: Customer orders and production progress
            - rowgroup [ref=f2e357]:
              - row [ref=f2e358]:
                - columnheader "Order" [ref=f2e359]
                - columnheader "Customer" [ref=f2e362]
                - columnheader "Grade" [ref=f2e363]
                - columnheader "Quantity" [ref=f2e364]
                - columnheader "Production" [ref=f2e365]
                - columnheader "Due · UTC" [ref=f2e366]
                - columnheader "Status" [ref=f2e367]
                - columnheader "Details" [ref=f2e368]
            - rowgroup [ref=f2e370]:
              - row [ref=f2e371]:
                - cell [ref=f2e372]:
                  - button "O-1001" [ref=f2e373] [cursor=pointer]
                - cell "Han River Fabrication KR" [ref=f2e374]:
                  - strong [ref=f2e375]: Han River Fabrication
                  - generic [ref=f2e376]: KR
                - cell "SPHC" [ref=f2e377]
                - cell "48 t" [ref=f2e378]
                - cell "0 0%" [ref=f2e379]:
                  - generic [ref=f2e380]:
                    - progressbar "O-1001 production" [ref=f2e381]
                    - generic [ref=f2e382]: 0%
                - cell "30 Oct 16:00" [ref=f2e383]:
                  - text: 30 Oct
                  - generic [ref=f2e384]: 16:00
                - cell "Producing" [ref=f2e385]
                - cell [ref=f2e388]:
                  - button "View order O-1001" [ref=f2e389] [cursor=pointer]
              - row [ref=f2e392]:
                - cell [ref=f2e393]:
                  - button "O-1002" [ref=f2e394] [cursor=pointer]
                - cell "Northstar Motors JP" [ref=f2e395]:
                  - strong [ref=f2e396]: Northstar Motors
                  - generic [ref=f2e397]: JP
                - cell "SS400" [ref=f2e398]
                - cell "50 t" [ref=f2e399]
                - cell "100 100%" [ref=f2e400]:
                  - generic [ref=f2e401]:
                    - progressbar "O-1002 production" [ref=f2e402]
                    - generic [ref=f2e404]: 100%
                - cell "30 Oct 15:00" [ref=f2e405]:
                  - text: 30 Oct
                  - generic [ref=f2e406]: 15:00
                - cell "Ready" [ref=f2e407]
                - cell [ref=f2e410]:
                  - button "View order O-1002" [ref=f2e411] [cursor=pointer]
              - row [ref=f2e414]:
                - cell [ref=f2e415]:
                  - button "O-1003" [ref=f2e416] [cursor=pointer]
                - cell "Harbor Construction AU" [ref=f2e417]:
                  - strong [ref=f2e418]: Harbor Construction
                  - generic [ref=f2e419]: AU
                - cell "SPCC" [ref=f2e420]
                - cell "52 t" [ref=f2e421]
                - cell "100 100%" [ref=f2e422]:
                  - generic [ref=f2e423]:
                    - progressbar "O-1003 production" [ref=f2e424]
                    - generic [ref=f2e426]: 100%
                - cell "30 Oct 14:00" [ref=f2e427]:
                  - text: 30 Oct
                  - generic [ref=f2e428]: 14:00
                - cell "At port" [ref=f2e429]
                - cell [ref=f2e432]:
                  - button "View order O-1003" [ref=f2e433] [cursor=pointer]
              - row [ref=f2e436]:
                - cell [ref=f2e437]:
                  - button "O-1004" [ref=f2e438] [cursor=pointer]
                - cell "Atlas Appliances KR" [ref=f2e439]:
                  - strong [ref=f2e440]: Atlas Appliances
                  - generic [ref=f2e441]: KR
                - cell "SPHC" [ref=f2e442]
                - cell "54 t" [ref=f2e443]
                - cell "100 100%" [ref=f2e444]:
                  - generic [ref=f2e445]:
                    - progressbar "O-1004 production" [ref=f2e446]
                    - generic [ref=f2e448]: 100%
                - cell "30 Oct 13:00" [ref=f2e449]:
                  - text: 30 Oct
                  - generic [ref=f2e450]: 13:00
                - cell "In transit" [ref=f2e451]
                - cell [ref=f2e454]:
                  - button "View order O-1004" [ref=f2e455] [cursor=pointer]
              - row [ref=f2e458]:
                - cell [ref=f2e459]:
                  - button "O-1005" [ref=f2e460] [cursor=pointer]
                - cell "Pacific Railworks JP" [ref=f2e461]:
                  - strong [ref=f2e462]: Pacific Railworks
                  - generic [ref=f2e463]: JP
                - cell "SS400" [ref=f2e464]
                - cell "56 t" [ref=f2e465]
                - cell "100 100%" [ref=f2e466]:
                  - generic [ref=f2e467]:
                    - progressbar "O-1005 production" [ref=f2e468]
                    - generic [ref=f2e470]: 100%
                - cell "30 Oct 12:00" [ref=f2e471]:
                  - text: 30 Oct
                  - generic [ref=f2e472]: 12:00
                - cell "In transit" [ref=f2e473]
                - cell [ref=f2e476]:
                  - button "View order O-1005" [ref=f2e477] [cursor=pointer]
              - row [ref=f2e480]:
                - cell [ref=f2e481]:
                  - button "O-1006" [ref=f2e482] [cursor=pointer]
                - cell "Summit Engineering AU" [ref=f2e483]:
                  - strong [ref=f2e484]: Summit Engineering
                  - generic [ref=f2e485]: AU
                - cell "SPCC" [ref=f2e486]
                - cell "58 t" [ref=f2e487]
                - cell "100 100%" [ref=f2e488]:
                  - generic [ref=f2e489]:
                    - progressbar "O-1006 production" [ref=f2e490]
                    - generic [ref=f2e492]: 100%
                - cell "30 Oct 11:00" [ref=f2e493]:
                  - text: 30 Oct
                  - generic [ref=f2e494]: 11:00
                - cell "In transit" [ref=f2e495]
                - cell [ref=f2e498]:
                  - button "View order O-1006" [ref=f2e499] [cursor=pointer]
        - generic [ref=f2e502]:
          - generic [ref=f2e503]: 6 of 6 orders
          - generic [ref=f2e504]: Synthetic data · SQLite persisted
      - generic [ref=f2e506]:
        - generic [ref=f2e507]:
          - text: SteelFlow 3D
          - generic [ref=f2e510]: /
          - text: Digital twin demonstration
        - generic [ref=f2e511]:
          - text: 100% synthetic data
          - generic [ref=f2e515]: ·
          - text: Deterministic simulation
      - status [ref=f2e516]: RECOVERY scenario. Step 2. Paused. orders records selected.
```

# Test source

```ts
  1   | import { test, expect, type Page, type APIRequestContext, type BrowserContext } from '@playwright/test';
  2   | import { mkdir } from 'node:fs/promises';
  3   | import { CoilDetailSchema, WorldSchema, type World } from '../src/contracts';
  4   | 
  5   | const evidence = 'docs/evidence';
  6   | const browserErrors = new WeakMap<BrowserContext, string[]>();
  7   | 
  8   | async function readWorld(request: APIRequestContext): Promise<World> {
  9   |   const response = await request.get('/api/v1/world');
  10  |   expect(response.ok()).toBe(true);
  11  |   return WorldSchema.parse(await response.json());
  12  | }
  13  | 
  14  | async function command(page: Page, label: string, path: string): Promise<World> {
> 15  |   const response = page.waitForResponse((item) => item.url().endsWith(path) && item.request().method() === 'POST');
      |                         ^ Error: page.waitForResponse: Test timeout of 45000ms exceeded.
  16  |   await page.getByRole('button', { name: label, exact: true }).click();
  17  |   const result = await response;
  18  |   expect(result.ok()).toBe(true);
  19  |   return WorldSchema.parse(await result.json());
  20  | }
  21  | 
  22  | function businessState(world: World) {
  23  |   return { orders: world.orders, lots: world.lots, coils: world.coils, inventory: world.inventory, shipments: world.shipments, shipment_coils: world.shipment_coils, kpis: world.kpis, risks: world.risks };
  24  | }
  25  | 
  26  | test.beforeEach(async ({ request, page, context }) => {
  27  |   const errors: string[] = [];
  28  |   browserErrors.set(context, errors);
  29  |   page.on('pageerror', (error) => errors.push(error.message));
  30  |   context.on('page', (opened) => opened.on('pageerror', (error) => errors.push(error.message)));
  31  |   await mkdir(evidence, { recursive: true });
  32  |   const response = await request.post('/api/v1/scenarios/NORMAL/activate');
  33  |   expect(response.ok()).toBe(true);
  34  |   await page.goto('/');
  35  |   await expect(page.getByRole('heading', { name: 'Operations overview' })).toBeVisible();
  36  | });
  37  | 
  38  | test.afterEach(async ({ context }, testInfo) => {
  39  |   const errors = browserErrors.get(context) ?? [];
  40  |   await testInfo.attach('uncaught-browser-errors', { body: JSON.stringify(errors), contentType: 'application/json' });
  41  |   expect(errors).toEqual([]);
  42  | });
  43  | 
  44  | test('3D factory renders, orbit and zoom respond, and no browser exception occurs', async ({ page }) => {
  45  |   const exceptions: string[] = [];
  46  |   page.on('pageerror', (error) => exceptions.push(error.message));
  47  |   await page.reload();
  48  |   const canvas = page.locator('canvas');
  49  |   await expect(canvas).toBeVisible();
  50  |   await expect(page.getByRole('button', { name: 'Advance one step', exact: true })).toBeEnabled();
  51  |   await page.screenshot({ path: `${evidence}/01-overview.png`, fullPage: true });
  52  |   const before = await canvas.screenshot();
  53  |   const box = await canvas.boundingBox();
  54  |   if (!box) throw new Error('3D canvas has no rendered bounding box');
  55  |   await page.getByRole('button', { name: 'Clear selection', exact: true }).click();
  56  |   await page.mouse.move(box.x + 520, box.y + 182);
  57  |   const tooltip = page.getByText(/^C-\d+ · \d+ t$/);
  58  |   await expect(tooltip).toBeVisible();
  59  |   const coilId = (await tooltip.innerText()).split(' · ')[0];
  60  |   if (!coilId) throw new Error('Hovered coil has no identity');
  61  |   await page.mouse.click(box.x + 520, box.y + 182);
  62  |   await expect(page.getByTestId('inspector').getByRole('heading', { name: coilId, exact: true })).toBeVisible();
  63  |   await page.screenshot({ path: `${evidence}/10-scene-coil-picking.png`, fullPage: true });
  64  |   await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
  65  |   await page.mouse.down();
  66  |   await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.6, { steps: 12 });
  67  |   await page.mouse.up();
  68  |   await page.mouse.wheel(0, -250);
  69  |   await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  70  |   await page.screenshot({ path: `${evidence}/02-orbit-zoom.png`, fullPage: true });
  71  |   expect(exceptions).toEqual([]);
  72  | });
  73  | 
  74  | test('search finds a customer order and empty search is explained', async ({ page }) => {
  75  |   const search = page.getByPlaceholder('Search orders, customers, grades…');
  76  |   await search.fill('Northstar');
  77  |   await expect(page.getByText('Northstar Motors', { exact: true }).first()).toBeVisible();
  78  |   await search.fill('nonexistent-order-98765');
  79  |   await expect(page.getByText('No matching orders', { exact: true })).toBeVisible();
  80  |   await page.screenshot({ path: `${evidence}/03-search-empty.png`, fullPage: true });
  81  |   await search.clear();
  82  |   await expect(page.getByText('Northstar Motors', { exact: true }).first()).toBeVisible();
  83  | });
  84  | 
  85  | test('accessible inventory selection exposes the exact coil relationships', async ({ page, request }) => {
  86  |   await page.getByRole('button', { name: '2D inventory', exact: true }).click();
  87  |   await expect(page.getByRole('region', { name: 'Core operational inventory' }).getByRole('table')).toBeVisible();
  88  |   await page.getByRole('button', { name: 'C-1005', exact: true }).click();
  89  |   const response = await request.get('/api/v1/coils/C-1005');
  90  |   expect(response.ok()).toBe(true);
  91  |   const detail = CoilDetailSchema.parse(await response.json());
  92  |   const inspector = page.getByTestId('inspector');
  93  |   await expect(inspector.getByRole('heading', { name: detail.coil.id, exact: true })).toBeVisible();
  94  |   await expect(inspector.getByRole('button', { name: detail.lot.id, exact: true })).toBeVisible();
  95  |   await expect(inspector.getByRole('button', { name: detail.order.id, exact: true })).toBeVisible();
  96  |   await expect(inspector.getByRole('button', { name: detail.location.name, exact: true })).toBeVisible();
  97  |   if (!detail.shipment) throw new Error('Seeded coil must have a shipment');
  98  |   await expect(inspector.getByRole('button', { name: detail.shipment.id, exact: true })).toBeVisible();
  99  |   await page.screenshot({ path: `${evidence}/04-inventory-coil.png`, fullPage: true });
  100 |   await inspector.getByRole('button', { name: detail.shipment.id, exact: true }).click();
  101 |   await expect(inspector.getByRole('list', { name: `Timeline for ${detail.shipment.id}` })).toBeVisible();
  102 |   await inspector.getByRole('button', { name: detail.order.id, exact: true }).click();
  103 |   await expect(inspector.getByRole('heading', { name: detail.order.id, exact: true })).toBeVisible();
  104 | });
  105 | 
  106 | test('three scenarios differ at the same tick and reset reproduces each baseline', async ({ page, request }) => {
  107 |   const results: Record<string, ReturnType<typeof businessState>> = {};
  108 |   for (const scenario of ['NORMAL', 'DELAY', 'RECOVERY']) {
  109 |     const activation = page.waitForResponse((response) => response.url().endsWith(`/scenarios/${scenario}/activate`));
  110 |     if (scenario === 'NORMAL') {
  111 |       await page.getByLabel('Scenario', { exact: true }).selectOption('DELAY');
  112 |       await expect.poll(async () => (await readWorld(request)).simulation.scenario_id).toBe('DELAY');
  113 |     }
  114 |     await page.getByLabel('Scenario', { exact: true }).selectOption(scenario);
  115 |     const baseline = WorldSchema.parse(await (await activation).json());
```