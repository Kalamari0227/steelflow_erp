import { z } from 'zod';

const color = z.string().regex(/^#[0-9a-f]{6}$/i);
const ratio = z.number().min(0).max(1);
const pbr = z.strictObject({ roughness: ratio, metalness: ratio });
const palette = z.strictObject({
  background: color, ground: color, shedBlue: color, shedTeal: color, structuralSteel: color,
  bareSteel: color, cranePaint: color, selectionAmber: color, hotMetal: color, routeTeal: color,
  road: color, rail: color, conveyor: color, hotMetalRail: color, water: color, text: color,
  mutedText: color, surface: color, border: color, blocked: color, offline: color, focus: color,
});
const mode = z.strictObject({ color: color, signature: z.string().min(1), routeOn: z.string().min(1) });
const cameraView = z.strictObject({ elevationDeg: z.number().min(10).max(80), paddingRatio: z.number().min(0.05).max(0.3) });
const tokenSchema = z.strictObject({
  version: z.literal(1), palette,
  materials: z.strictObject({ paintedShed: pbr, structuralSteel: pbr, bareSteel: pbr, road: pbr, ground: pbr, water: pbr }),
  lighting: z.strictObject({ keyColor: color, fillColor: color, keyIntensity: z.number().positive(), fillIntensity: z.number().positive(),
    keyDirection: z.tuple([z.number(), z.number().positive(), z.number()]), shadowOpacity: ratio,
    shadowSoftnessM: z.number().positive(), exposure: z.number().positive(), bloom: z.literal(false) }),
  world: z.strictObject({ units: z.literal('m'), up: z.literal('+Y'), forward: z.literal('+X'), physicalScale: z.literal(1),
    environmentScale: z.literal('world_meters'), materialDimensionConversion: z.literal('mm_divided_by_1000'), screenshotPlane: z.literal(false) }),
  transport: z.strictObject({ road: mode, dispatchRail: mode, hotMetalRail: mode, conveyor: mode, sea: mode }),
  selection: z.strictObject({ color: color, emissiveIntensity: z.literal(0), outlinePx: z.number().min(1).max(3),
    physicalCopies: z.literal(1), routeWidthPx: z.number().min(1).max(3), routeOpacity: ratio }),
  heat: z.strictObject({ color: color, maxEmissiveIntensity: z.number().min(0).max(2), source: z.literal('server_material_state'), calibratedTemperature: z.literal(false) }),
  labels: z.strictObject({ fontPx: z.number().min(12), selectedFontPx: z.number().min(14), maxWidthPx: z.number().max(180).positive(),
    maxLines: z.literal(2), backgroundOpacity: z.literal(0), maxOverviewLabels: z.number().int().positive(),
    equipmentOverlapRatio: z.literal(0), gapPx: z.number().min(8), occlusion: z.literal('hide_then_edge_callout'), priority: z.tuple([z.literal('selected'), z.literal('blocked'), z.literal('zone')]) }),
  overlay: z.strictObject({ desktopPanelPx: z.number().min(220).max(300), edgeGapPx: z.number().min(12),
    minimumSceneWidthRatio: z.number().min(0.8).max(1), compactBreakpointPx: z.number().positive(),
    compactPanel: z.literal('collapsible_below_viewport'), sceneSafeRect: z.literal('exclude_panels_and_controls') }),
  typography: z.strictObject({ family: z.string().min(1), bodyPx: z.number().min(14), compactBodyPx: z.number().min(17),
    lineHeight: z.number().min(1.4), weights: z.tuple([z.literal(400), z.literal(500), z.literal(600)]) }),
  camera: z.strictObject({ overview: cameraView, detail: cameraView, follow: cameraView,
    pan: z.strictObject({ buttons: z.tuple([z.literal('north'), z.literal('south'), z.literal('east'), z.literal('west')]),
      plane: z.literal('ground_xz_camera_relative'), stepViewportRatio: z.number().min(0.02).max(0.2), changesSimulation: z.literal(false) }),
    orbit: z.strictObject({ minPolarDeg: z.number().min(5), maxPolarDeg: z.number().max(85), target: z.literal('selected_or_world_center') }),
    zoom: z.strictObject({ minDistanceM: z.number().positive(), maxDistanceM: z.number().positive(), anchor: z.literal('cursor_or_target') }),
    followPolicy: z.literal('same_entity_manual_input_suspends'), cutaway: z.literal('same_root_hide_shell_only') }),
  motion: z.strictObject({ clock: z.literal('server_sim_ms'), speeds: z.tuple([z.literal(1), z.literal(2), z.literal(4)]),
    speedApplications: z.literal(1), pause: z.literal('freeze_pose_and_attachment'), stale: z.literal('freeze_last_confirmed_snapshot'),
    reduced: z.literal('disable_camera_easing_and_decor_preserve_physics'), decorativeWork: z.literal(false), transitionMs: z.number().min(0).max(300) }),
  states: z.strictObject({ normal: z.literal('state_bound_motion'), waiting: z.literal('stationary_reason_label'), blocked: z.literal('stationary_warning_and_reason'),
    paused: z.literal('frozen_pose_pause_glyph'), resumed: z.literal('same_state_continuation'), offline: z.literal('last_confirmed_state_offline_label'),
    error: z.literal('inline_reason_retry_without_reset'), selected: z.literal('one_amber_contour_and_details') }),
  accessibility: z.strictObject({ targetPx: z.number().min(44), targetGapPx: z.number().min(8), bodyContrast: z.number().min(4.5),
    controlContrast: z.number().min(3), keyboard: z.literal(true), colorOnlyStatus: z.literal(false), tableEquivalent: z.literal(true) }),
  lod: z.strictObject({ thresholdsM: z.tuple([z.number().positive(), z.number().positive()]), hysteresisRatio: z.number().min(0.05).max(0.3),
    equalPolygonCount: z.literal(false), preserve: z.tuple([z.literal('run'), z.literal('entity'), z.literal('variant'), z.literal('attachment'), z.literal('socket'), z.literal('sim_ms'), z.literal('selection')]) }),
}).superRefine((value, ctx) => {
  const selection = value.palette.selectionAmber.toLowerCase();
  const heat = value.palette.hotMetal.toLowerCase();
  if (selection === heat || value.selection.color.toLowerCase() !== selection || value.heat.color.toLowerCase() !== heat)
    ctx.addIssue({ code: 'custom', message: 'selection and physical heat must have separate consistent semantics' });
  if (value.camera.orbit.minPolarDeg >= value.camera.orbit.maxPolarDeg || value.camera.zoom.minDistanceM >= value.camera.zoom.maxDistanceM || value.lod.thresholdsM[0] >= value.lod.thresholdsM[1])
    ctx.addIssue({ code: 'custom', message: 'ordered camera and LOD bounds required' });
});

export type VisualTokens = z.infer<typeof tokenSchema>;

/** Art-direction decisions from A/B/C, not measured plant dimensions or sensor calibration. */
export const visualTokens = {
  version: 1,
  palette: {
    background: '#f7f5ef', ground: '#e8e4d9', shedBlue: '#7895a5', shedTeal: '#638f94', structuralSteel: '#58656c',
    bareSteel: '#aeb8bb', cranePaint: '#ce8c39', selectionAmber: '#b86b00', hotMetal: '#ff581c', routeTeal: '#317f82',
    road: '#777b7b', rail: '#555a62', conveyor: '#817b65', hotMetalRail: '#a27457', water: '#83b4c4', text: '#25313d',
    mutedText: '#52606b', surface: '#fffefa', border: '#c8cccb', blocked: '#b33431', offline: '#63717c', focus: '#175d87',
  },
  materials: {
    paintedShed: { roughness: 0.72, metalness: 0.12 }, structuralSteel: { roughness: 0.55, metalness: 0.72 },
    bareSteel: { roughness: 0.38, metalness: 0.9 }, road: { roughness: 0.95, metalness: 0 },
    ground: { roughness: 0.92, metalness: 0 }, water: { roughness: 0.28, metalness: 0 },
  },
  lighting: { keyColor: '#fff2db', fillColor: '#e6eff6', keyIntensity: 2.4, fillIntensity: 1.1,
    keyDirection: [-0.6, 1, 0.5], shadowOpacity: 0.22, shadowSoftnessM: 1.2, exposure: 1, bloom: false },
  world: { units: 'm', up: '+Y', forward: '+X', physicalScale: 1, environmentScale: 'world_meters', materialDimensionConversion: 'mm_divided_by_1000', screenshotPlane: false },
  transport: {
    road: { color: '#777b7b', signature: 'paved_lanes_markings_turning_aprons', routeOn: 'actual_lane' },
    dispatchRail: { color: '#555a62', signature: 'paired_rails_sleepers_switches', routeOn: 'actual_track' },
    hotMetalRail: { color: '#a27457', signature: 'dedicated_track_torpedo_ladle_warning_markers', routeOn: 'dedicated_hot_metal_track' },
    conveyor: { color: '#817b65', signature: 'raised_belt_idlers_trestles_chutes', routeOn: 'actual_belt' },
    sea: { color: '#83b4c4', signature: 'water_berth_channel_boundary', routeOn: 'navigable_channel' },
  },
  selection: { color: '#b86b00', emissiveIntensity: 0, outlinePx: 2, physicalCopies: 1, routeWidthPx: 2, routeOpacity: 0.45 },
  heat: { color: '#ff581c', maxEmissiveIntensity: 1.4, source: 'server_material_state', calibratedTemperature: false },
  labels: { fontPx: 12, selectedFontPx: 14, maxWidthPx: 160, maxLines: 2, backgroundOpacity: 0,
    maxOverviewLabels: 8, equipmentOverlapRatio: 0, gapPx: 8, occlusion: 'hide_then_edge_callout', priority: ['selected', 'blocked', 'zone'] },
  overlay: { desktopPanelPx: 248, edgeGapPx: 16, minimumSceneWidthRatio: 0.8, compactBreakpointPx: 1280,
    compactPanel: 'collapsible_below_viewport', sceneSafeRect: 'exclude_panels_and_controls' },
  typography: { family: '-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif', bodyPx: 14, compactBodyPx: 17, lineHeight: 1.5, weights: [400, 500, 600] },
  camera: {
    overview: { elevationDeg: 42, paddingRatio: 0.12 }, detail: { elevationDeg: 32, paddingRatio: 0.15 }, follow: { elevationDeg: 38, paddingRatio: 0.18 },
    pan: { buttons: ['north', 'south', 'east', 'west'], plane: 'ground_xz_camera_relative', stepViewportRatio: 0.08, changesSimulation: false },
    orbit: { minPolarDeg: 12, maxPolarDeg: 80, target: 'selected_or_world_center' },
    zoom: { minDistanceM: 2, maxDistanceM: 3000, anchor: 'cursor_or_target' },
    followPolicy: 'same_entity_manual_input_suspends', cutaway: 'same_root_hide_shell_only',
  },
  motion: { clock: 'server_sim_ms', speeds: [1, 2, 4], speedApplications: 1, pause: 'freeze_pose_and_attachment',
    stale: 'freeze_last_confirmed_snapshot', reduced: 'disable_camera_easing_and_decor_preserve_physics', decorativeWork: false, transitionMs: 180 },
  states: { normal: 'state_bound_motion', waiting: 'stationary_reason_label', blocked: 'stationary_warning_and_reason', paused: 'frozen_pose_pause_glyph',
    resumed: 'same_state_continuation', offline: 'last_confirmed_state_offline_label', error: 'inline_reason_retry_without_reset', selected: 'one_amber_contour_and_details' },
  accessibility: { targetPx: 44, targetGapPx: 8, bodyContrast: 4.5, controlContrast: 3, keyboard: true, colorOnlyStatus: false, tableEquivalent: true },
  lod: { thresholdsM: [180, 650], hysteresisRatio: 0.1, equalPolygonCount: false, preserve: ['run', 'entity', 'variant', 'attachment', 'socket', 'sim_ms', 'selection'] },
} as const satisfies VisualTokens;

export function parseVisualTokens(input: unknown): VisualTokens { return tokenSchema.parse(input); }
