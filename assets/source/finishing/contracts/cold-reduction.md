# R6-21D2 / Q2 — sealed cold reduction correction

Status: **DECISION SEALED; source-bound numeric and actual Python/TypeScript metadata admission PASS.** This is not decoded finishing GLB/contact acceptance. Original `preparation/handoff.md` remains unchanged, SHA256 `9a01d26849980ba5b5f93079cc73f78d6ad633eeb6b777cd2dbbbb87cdb2a69f`. Native assigned role is Astra High; no independent hidden runtime/model attestation is available. No Ultra use. T21 clock and whole-family criteria remain unchanged.

## Exact law and authored range

Current `assets/source/finishing/rolling.py` has first cold work-roll R=.36 m, lower center y=datum−R and upper center y=datum+.002+R. Keep these stand positions/radii, input 4×1.2×.004 m, output 8×1.2×.002 m, and constant volume .0192 m³. Use the first nip's local x coordinate as x=0; its actual owner-local offset is −2.475 m (CR) or −.825 m (GO/NGO).

Let Tin=.004, Tout=.002, L=4, W=1.2, R=.36. Set b=sqrt(R²−(R−(Tin−Tout)/2)²)=.026814175355583798 m and β=asin(b/R)=.07455286365336057 rad. Define t(x)=Tin upstream x≤−b; t(x)=Tout+2(R−sqrt(R²−x²)) for −b≤x≤0; t(x)=Tout downstream x≥0. Define A(x)=∫[-b,x]t(s)/Tout ds with the same upstream/downstream extensions. It is strictly increasing. A(0)=.03574726230069509 m.

The sole feed scalar is q=Rθ from the admitted **cold_reduction_roll** channel. For the original Lagrangian coordinate u∈[0,4] measured backwards from the leading tip, x(u,θ)=A⁻¹(q−(Tin/Tout)u). Cross-section center is y=datum+Tout/2, width coordinate z∈[−W/2,W/2], top/bottom y=center±t(x)/2. This law applies over the entire closed range, including bite entry and the last tail, without changing the business version during forming.

New T21 instance range: **min0, max22.32152017305749 rad, rest0**, derived as (L Tin/Tout+A(0))/R. This explicitly supersedes only the old T21 cold `8/R=22.22222222222222` endpoint; it changes no global range rule, stock target or existing T12/T20/T62 instance. Author source recipe, manifest moving part, same node clip samples, canonical binding and forming descriptor from the one stored maximum. Reject larger θ; no epsilon expansion. Floating-point evaluation may use the mathematically identical exact endpoint q=8+A(0) when θ equals the stored maximum; it must not snap a non-endpoint vertex or accept overshoot.

At θ0: x_tip=−b, x_tail=−4−b, full raw length exactly4, thickness4mm everywhere. At θ=A(0)/R=.09929795083526415: tip reaches nip, length4.008940544205237; it is truthfully partly processed. At old8/R: tail only reaches bite entry and length7.991066913054889; not complete. At new maximum: tail=0, tip=8, all material2mm. Volume W Tout[A(x_tip)−A(x_tail)]=W Tin L at every θ, not just endpoints. The numeric probe evaluates 2001 phases, max volume error6.94e−18 m³.

## Actual material contact through entry and tail

The original canonical `work` datum is not occupied at θ0 and cannot be claimed as the full-cycle contact. Keep that socket unchanged. Add three actual support sockets to the new cold asset and a monotonic derived fixture world (all family STRIP):

1. `cold_entry_support`, fixed lower-roll bite-entry surface: (nip_x−b, datum−(Tin−Tout)/2,0). Use θ∈[0,8/R]. The finite material occupies this exact point throughout that interval.
2. `cold_bite_roll_support`, on the actual lower **cold_reduction_roll** node and its real surface, with motion chain containing that existing function. At θ₁=8/R its world point equals socket1. Author its rest point as pivot+Rz(+θ₁)·(−b,R−(Tin−Tout)/2,0), because canonical axis is −Z. Use θ∈[θ₁,θ₁+β]. For δ=θ−θ₁ the contact x=−R sin(β−δ), y=datum−R+R cos(β−δ). This stays on the lower material face and the actual roll surface. It advances ahead of the tail: dA(x_contact)/dδ=R(t/Tout)cos(β−δ)≥R. Thus the whole material still covers it.
3. `cold_nip_support`, fixed (nip_x,datum,0). At θ₂=22.29677508587558 it is exactly the same physical point as socket2. Use through θmax; the tail then advances from−.008612454420303842 to0 while the nip remains occupied.

Each switch is an explicit same-time old release/new acquire with retained attachments, exact same material ID and version, previous anchor and channel values. Both boundary requests pass actual candidate Python/TypeScript CLIs with contact difference below1e−12 m. No new function or generic motion wire is required. Rotation-marker material slip is permitted by this kinematic forming view; this is not a rolling-force/friction model. The all-phase contact proof is analytic; Sol must additionally test actual decoded triangles, dual normals, signed clearance and all three LODs.

The family renderer may express the analytic vertices in the actual admitted moving-anchor coordinate system using its inverse transform. It must then prove every world vertex against the analytic law; it must not reset the pose to the work datum. At each retained switch M_new v_new=M_old v_old within1e−6 m and identical topology are mandatory. Changing support frames must preserve the one connected finite sheet; use the same material/immutable version until explicit completion. Completion adds a distinct THIN_STRIP version with 8m×1.2m×2mm dimensions and retained batch IO/edge/history; CR04's later intermediate winding to CR_COIL is a further distinct subphase/version, not a shortcut from raw4mm strip to coil.

## Sol ownership and evidence

`r6_finishing_assets` owns only its already assigned `assets/source/finishing/rolling.py`, `recipe.json`/generated descriptors, `manifest.py`, and `tests/fixtures/finishing/{forming.ts,poses.ts,material.tsx,diagnostics.tsx}` plus owned tests/output roots. Author the three sockets with actual nodes, independent retained records and the corrected fixed clip range. No shared T62/core/canonical-world file edit is authorized by this note.

Invocation: `backend/.venv/bin/python .omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21/preparation/continuity-02/probe.py`.

Fresh passing run: `run-104510-51f296b8/`. Numeric artifact: `cold-math.json`. Actual request/output artifacts: `cold-*.json`, `candidate/cold-*/{python,typescript}/{stdout.log,receipt.json}`. Binary observables: nine accepted cold scenarios (entry, partial, both before/after boundaries, tail completion), overshoot rejected `binding` in both runtimes, boundary contacts equal, 2001 analytic samples finite and volume conserved. `preflight.json` pins actual MAIN/candidate sources and original handoff; `result.json` confirms core source bytes unchanged, all child commands returned, no server/port/DB. Full run also includes Q1 admission checks; it is not T64's independent gate.
