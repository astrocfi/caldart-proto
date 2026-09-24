/**
 * Common general aviation types, by ICAO designator.
 *
 * The register is typed in by hand, so the same airframe arrives as "172",
 * "172S", "C172S" and "Skyhawk". This list is what the model field suggests:
 * pick one and the make fills itself in, and the register ends up with one
 * spelling per type.
 *
 * It is deliberately the light end of ICAO DOC 8643 — the aircraft a DART
 * actually flies — rather than the whole document. A type that is missing is
 * still typed in freely; nothing here is enforced.
 */

export interface AircraftType {
  /** The ICAO type designator, e.g. `C172`. */
  designator: string;
  make: string;
  model: string;
}

export const AIRCRAFT_TYPES: readonly AircraftType[] = [
  // -- Cessna ---------------------------------------------------------------
  { designator: 'C150', make: 'Cessna', model: '150' },
  { designator: 'C152', make: 'Cessna', model: '152' },
  { designator: 'C162', make: 'Cessna', model: '162 Skycatcher' },
  { designator: 'C170', make: 'Cessna', model: '170' },
  { designator: 'C172', make: 'Cessna', model: '172 Skyhawk' },
  { designator: 'C175', make: 'Cessna', model: '175 Skylark' },
  { designator: 'C177', make: 'Cessna', model: '177 Cardinal' },
  { designator: 'C180', make: 'Cessna', model: '180 Skywagon' },
  { designator: 'C182', make: 'Cessna', model: '182 Skylane' },
  { designator: 'C185', make: 'Cessna', model: '185 Skywagon' },
  { designator: 'C188', make: 'Cessna', model: '188 Ag Wagon' },
  { designator: 'C195', make: 'Cessna', model: '195 Businessliner' },
  { designator: 'C206', make: 'Cessna', model: '206 Stationair' },
  { designator: 'C207', make: 'Cessna', model: '207 Skywagon' },
  { designator: 'C208', make: 'Cessna', model: '208 Caravan' },
  { designator: 'C210', make: 'Cessna', model: '210 Centurion' },
  { designator: 'C310', make: 'Cessna', model: '310' },
  { designator: 'C337', make: 'Cessna', model: '337 Skymaster' },
  { designator: 'C340', make: 'Cessna', model: '340' },
  { designator: 'C414', make: 'Cessna', model: '414 Chancellor' },
  { designator: 'C421', make: 'Cessna', model: '421 Golden Eagle' },
  { designator: 'C425', make: 'Cessna', model: '425 Conquest I' },
  { designator: 'C441', make: 'Cessna', model: '441 Conquest II' },
  { designator: 'C25A', make: 'Cessna', model: 'Citation CJ2' },
  { designator: 'C25B', make: 'Cessna', model: 'Citation CJ3' },
  { designator: 'C56X', make: 'Cessna', model: 'Citation Excel' },

  // -- Piper ----------------------------------------------------------------
  { designator: 'J3', make: 'Piper', model: 'J-3 Cub' },
  { designator: 'PA11', make: 'Piper', model: 'PA-11 Cub Special' },
  { designator: 'PA12', make: 'Piper', model: 'PA-12 Super Cruiser' },
  { designator: 'PA18', make: 'Piper', model: 'PA-18 Super Cub' },
  { designator: 'PA20', make: 'Piper', model: 'PA-20 Pacer' },
  { designator: 'PA22', make: 'Piper', model: 'PA-22 Tri-Pacer' },
  { designator: 'PA23', make: 'Piper', model: 'PA-23 Aztec' },
  { designator: 'PA24', make: 'Piper', model: 'PA-24 Comanche' },
  { designator: 'PA25', make: 'Piper', model: 'PA-25 Pawnee' },
  { designator: 'P28A', make: 'Piper', model: 'PA-28 Cherokee' },
  { designator: 'P28B', make: 'Piper', model: 'PA-28 Dakota' },
  { designator: 'P28R', make: 'Piper', model: 'PA-28R Arrow' },
  { designator: 'PA30', make: 'Piper', model: 'PA-30 Twin Comanche' },
  { designator: 'PA31', make: 'Piper', model: 'PA-31 Navajo' },
  { designator: 'P32R', make: 'Piper', model: 'PA-32R Saratoga' },
  { designator: 'PA32', make: 'Piper', model: 'PA-32 Cherokee Six' },
  { designator: 'PA34', make: 'Piper', model: 'PA-34 Seneca' },
  { designator: 'PA38', make: 'Piper', model: 'PA-38 Tomahawk' },
  { designator: 'PA44', make: 'Piper', model: 'PA-44 Seminole' },
  { designator: 'PA46', make: 'Piper', model: 'PA-46 Malibu' },
  { designator: 'P46T', make: 'Piper', model: 'PA-46 Malibu Meridian' },
  { designator: 'PA47', make: 'Piper', model: 'PA-47 PiperJet' },

  // -- Beechcraft -----------------------------------------------------------
  { designator: 'BE23', make: 'Beechcraft', model: 'Model 23 Musketeer' },
  { designator: 'BE24', make: 'Beechcraft', model: 'Model 24 Sierra' },
  { designator: 'BE33', make: 'Beechcraft', model: 'Model 33 Debonair' },
  { designator: 'BE35', make: 'Beechcraft', model: 'Model 35 Bonanza' },
  { designator: 'BE36', make: 'Beechcraft', model: 'Model 36 Bonanza' },
  { designator: 'BE55', make: 'Beechcraft', model: 'Model 55 Baron' },
  { designator: 'BE58', make: 'Beechcraft', model: 'Model 58 Baron' },
  { designator: 'BE60', make: 'Beechcraft', model: 'Model 60 Duke' },
  { designator: 'BE76', make: 'Beechcraft', model: 'Model 76 Duchess' },
  { designator: 'BE77', make: 'Beechcraft', model: 'Model 77 Skipper' },
  { designator: 'BE9L', make: 'Beechcraft', model: 'King Air 90' },
  { designator: 'BE20', make: 'Beechcraft', model: 'King Air 200' },
  { designator: 'BE35', make: 'Beechcraft', model: 'V35 Bonanza' },
  { designator: 'BE18', make: 'Beechcraft', model: 'Model 18 Twin Beech' },

  // -- Cirrus, Diamond, Mooney ---------------------------------------------
  { designator: 'SR20', make: 'Cirrus', model: 'SR20' },
  { designator: 'SR22', make: 'Cirrus', model: 'SR22' },
  { designator: 'S22T', make: 'Cirrus', model: 'SR22T' },
  { designator: 'SF50', make: 'Cirrus', model: 'SF50 Vision Jet' },
  { designator: 'DA20', make: 'Diamond', model: 'DA20 Katana' },
  { designator: 'DA40', make: 'Diamond', model: 'DA40 Diamond Star' },
  { designator: 'DA42', make: 'Diamond', model: 'DA42 Twin Star' },
  { designator: 'DA62', make: 'Diamond', model: 'DA62' },
  { designator: 'M20P', make: 'Mooney', model: 'M20 Ovation' },
  { designator: 'M20T', make: 'Mooney', model: 'M20 Acclaim' },

  // -- Grumman, Maule, Aviat, Husky ----------------------------------------
  { designator: 'AA1', make: 'Grumman', model: 'AA-1 Yankee' },
  { designator: 'AA5', make: 'Grumman', model: 'AA-5 Tiger' },
  { designator: 'MX7', make: 'Maule', model: 'M-7 Super Rocket' },
  { designator: 'BL8', make: 'Aviat', model: 'A-1 Husky' },
  { designator: 'PTS2', make: 'Aviat', model: 'Pitts S-2' },
  { designator: 'CH7A', make: 'Champion', model: '7 Citabria' },
  { designator: 'DECA', make: 'Champion', model: '8KCAB Decathlon' },
  { designator: 'BL17', make: 'Bellanca', model: '17-30 Viking' },

  // -- Experimental and kit -------------------------------------------------
  { designator: 'RV4', make: "Van's", model: 'RV-4' },
  { designator: 'RV6', make: "Van's", model: 'RV-6' },
  { designator: 'RV7', make: "Van's", model: 'RV-7' },
  { designator: 'RV8', make: "Van's", model: 'RV-8' },
  { designator: 'RV9', make: "Van's", model: 'RV-9' },
  { designator: 'RV10', make: "Van's", model: 'RV-10' },
  { designator: 'RV12', make: "Van's", model: 'RV-12' },
  { designator: 'RV14', make: "Van's", model: 'RV-14' },
  { designator: 'LNC2', make: 'Lancair', model: '235/320/360' },
  { designator: 'LNC4', make: 'Lancair', model: 'IV' },
  { designator: 'GLST', make: 'Glasair', model: 'Glasair III' },
  { designator: 'VELO', make: 'Velocity', model: 'Velocity' },
  { designator: 'KITF', make: 'Kitfox', model: 'Kitfox' },
  { designator: 'SNKY', make: 'Rans', model: 'S-7 Courier' },

  // -- Light sport ----------------------------------------------------------
  { designator: 'CTLS', make: 'Flight Design', model: 'CTLS' },
  { designator: 'ICON', make: 'Icon', model: 'A5' },
  { designator: 'SLG2', make: 'Pipistrel', model: 'Sinus' },
  { designator: 'VIRU', make: 'Pipistrel', model: 'Virus' },
  { designator: 'TECN', make: 'Tecnam', model: 'P2008' },
  { designator: 'P2006', make: 'Tecnam', model: 'P2006T' },

  // -- Amphibian and utility ------------------------------------------------
  { designator: 'DHC2', make: 'de Havilland Canada', model: 'DHC-2 Beaver' },
  { designator: 'DHC6', make: 'de Havilland Canada', model: 'DHC-6 Twin Otter' },
  { designator: 'LAKE', make: 'Lake', model: 'LA-4 Buccaneer' },
  { designator: 'AC11', make: 'Aero Commander', model: '100 Darter' },
  { designator: 'AC50', make: 'Aero Commander', model: '500 Shrike' },
  { designator: 'PC12', make: 'Pilatus', model: 'PC-12' },
  { designator: 'TBM7', make: 'Daher', model: 'TBM 700' },
  { designator: 'TBM9', make: 'Daher', model: 'TBM 900' },
  { designator: 'EPIC', make: 'Epic', model: 'E1000' },

  // -- Helicopters ----------------------------------------------------------
  { designator: 'R22', make: 'Robinson', model: 'R22' },
  { designator: 'R44', make: 'Robinson', model: 'R44' },
  { designator: 'R66', make: 'Robinson', model: 'R66' },
  { designator: 'B06', make: 'Bell', model: '206 JetRanger' },
  { designator: 'B407', make: 'Bell', model: '407' },
  { designator: 'AS50', make: 'Airbus', model: 'AS350 Ecureuil' },
  { designator: 'H125', make: 'Airbus', model: 'H125' },
  { designator: 'EC30', make: 'Airbus', model: 'H130' },
  { designator: 'S76', make: 'Sikorsky', model: 'S-76' },
  { designator: 'MD5N', make: 'MD Helicopters', model: 'MD 500' },
];

/** Suggestions for what has been typed so far, best first, at most `limit`. */
export function suggestTypes(typed: string, limit = 8): AircraftType[] {
  const term = typed.trim().toLowerCase();
  if (term.length < 2) return [];

  const scored = AIRCRAFT_TYPES.map((type) => {
    const model = type.model.toLowerCase();
    const haystack = `${type.make} ${type.model} ${type.designator}`.toLowerCase();
    if (model.startsWith(term)) return { type, rank: 0 };
    if (type.designator.toLowerCase().startsWith(term)) return { type, rank: 1 };
    if (haystack.includes(term)) return { type, rank: 2 };
    return { type, rank: 99 };
  }).filter((entry) => entry.rank < 99);

  scored.sort((a, b) => a.rank - b.rank || a.type.model.localeCompare(b.type.model));
  return scored.slice(0, limit).map((entry) => entry.type);
}

/** The catalog entry whose model is exactly `typed`, if there is just one. */
export function matchType(typed: string): AircraftType | null {
  const term = typed.trim().toLowerCase();
  const matches = AIRCRAFT_TYPES.filter((type) => type.model.toLowerCase() === term);
  return matches.length === 1 ? (matches[0] ?? null) : null;
}
