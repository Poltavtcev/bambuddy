import type { TFunction } from 'i18next';

/** Map backend English maintenance type names to i18n keys under maintenance.types.* */
const NAME_TO_TYPE_KEY: Record<string, string> = {
  'Lubricate Carbon Rods': 'lubricateCarbonRods',
  'Lubricate Linear Rails': 'lubricateRails',
  'Clean Nozzle/Hotend': 'cleanNozzle',
  'Check Belt Tension': 'checkBelts',
  'Clean Build Plate': 'cleanBuildPlate',
  'Check Extruder Gears': 'checkExtruder',
  'Check Cooling Fans': 'checkCooling',
  'General Inspection': 'generalInspection',
  'Clean Carbon Rods': 'cleanCarbonRods',
  'Lubricate Steel Rods': 'lubricateSteelRods',
  'Clean Steel Rods': 'cleanSteelRods',
  'Clean Linear Rails': 'cleanLinearRails',
  'Check PTFE Tube': 'checkPtfeTube',
  'Replace HEPA Filter': 'replaceHepaFilter',
  'Replace Carbon Filter': 'replaceCarbonFilter',
  'Lubricate Left Nozzle Rail': 'lubricateLeftNozzleRail',
  'HEPA Filter': 'replaceHepaFilter',
  'Carbon Filter': 'replaceCarbonFilter',
  'Left Nozzle Rail': 'lubricateLeftNozzleRail',
};

export function getMaintenanceTypeLabel(t: TFunction, name: string): string {
  const key = NAME_TO_TYPE_KEY[name];
  return key ? t(`maintenance.types.${key}`) : name;
}

export function getMaintenanceTypeDescription(t: TFunction, name: string): string | null {
  const key = NAME_TO_TYPE_KEY[name];
  return key ? t(`maintenanceDescriptions.${key}`) : null;
}
