export function requiredEnv(name) {
  const value = __ENV[name];
  if (value === undefined || value === "") {
    throw new Error(`missing required env: ${name} (set in .env.load or .env.k6)`);
  }
  return value;
}

export function optionalEnv(name, defaultValue) {
  const value = __ENV[name];
  if (value === undefined || value === "") {
    return defaultValue;
  }
  return value;
}

export function envInt(name, defaultValue) {
  return Number(optionalEnv(name, String(defaultValue)));
}

/** UTC timestamps for Grafana/Prometheus window (printed together at test end). */
export function loadTestSetup() {
  return { t0: new Date().toISOString() };
}

export function loadTestTeardown(data) {
  const t0 = data?.t0 ?? "unknown";
  const t1 = new Date().toISOString();
  console.log("--- load-test window (UTC, copy to Grafana) ---");
  console.log(`LOAD_TEST_T0=${t0}`);
  console.log(`LOAD_TEST_T1=${t1}`);
  console.log(`LOAD_TEST_WINDOW=${t0} .. ${t1}`);
  console.log("Grafana: [T0, T1 + handler tail] — extend past T1 for /run suspense and polling drain");
  console.log("----------------------------------------------");
}

const HTTP_THRESHOLD = {
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

/** Ramp: startRate → peak (ramp up) → peak (plateau) → end (ramp down). */
export function rampOptions(botCount, scenarioName = "ramp") {
  const peak = Number(requiredEnv("LOAD_RAMP_RPS_PEAK"));
  const wing = Math.max(1, Math.round(peak / 5));
  const start = envInt("LOAD_RAMP_RPS_START", wing);
  const end = envInt("LOAD_RAMP_RPS_END", wing);
  const rampUp = optionalEnv("LOAD_RAMP_STAGE_RAMP_UP", "30s");
  const plateau = optionalEnv("LOAD_RAMP_STAGE_PLATEAU", "1m");
  const rampDown = optionalEnv("LOAD_RAMP_STAGE_RAMP_DOWN", "30s");
  const maxVUs = envInt(
    "LOAD_RAMP_MAX_VUS",
    Math.max(botCount, peak, 100),
  );
  const preAllocatedVUs = envInt(
    "LOAD_RAMP_PREALLOCATED_VUS",
    Math.min(20, maxVUs),
  );

  return {
    scenarios: {
      [scenarioName]: {
        executor: "ramping-arrival-rate",
        startRate: start,
        timeUnit: "1s",
        preAllocatedVUs,
        maxVUs,
        stages: [
          { target: peak, duration: rampUp },
          { target: peak, duration: plateau },
          { target: end, duration: rampDown },
        ],
      },
    },
    ...HTTP_THRESHOLD,
  };
}

export function runHappyOptions(botCount) {
  const vus = envInt("LOAD_RUN_HAPPY_VUS", botCount);
  const maxDuration = optionalEnv("LOAD_RUN_HAPPY_MAX_DURATION", "30m");

  return {
    scenarios: {
      draw_happy: {
        executor: "per-vu-iterations",
        vus,
        iterations: 1,
        maxDuration,
      },
    },
    ...HTTP_THRESHOLD,
  };
}

export function runContentionOptions(vus, iterations) {
  const maxDuration = optionalEnv("LOAD_CONTENTION_MAX_DURATION", "10m");

  return {
    scenarios: {
      draw_contention: {
        executor: "shared-iterations",
        vus,
        iterations,
        maxDuration,
      },
    },
    ...HTTP_THRESHOLD,
  };
}
