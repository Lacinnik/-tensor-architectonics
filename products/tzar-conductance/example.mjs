export const example = {
  source: {
    invariant: {
      constructId: "TZAR-DECLARATION-001",
      author: "Александр Лацинник",
      axisTerm: "осевание",
      axisDefinition: "Осевание — приведение субъектной структуры в состояние, при котором супра становится сущей.",
      version: "1.0.0",
      status: "canonical"
    }
  },
  forms: [
    {
      label: "Линейная форма",
      representation: { geometry: "Euclid", model: "ordered-linear" },
      invariant: {
        constructId: "TZAR-DECLARATION-001",
        author: "Александр Лацинник",
        axisTerm: "осевание",
        axisDefinition: "Осевание — приведение субъектной структуры в состояние, при котором супра становится сущей.",
        version: "1.0.0",
        status: "canonical"
      }
    },
    {
      label: "Граф отношений",
      representation: { geometry: "Projective", model: "relation-graph" },
      invariant: {
        constructId: "TZAR-DECLARATION-001",
        author: "Александр Лацинник",
        axisTerm: "осевание",
        axisDefinition: "Осевание — приведение субъектной структуры в состояние, при котором супра становится сущей.",
        version: "1.0.0",
        status: "canonical"
      }
    },
    {
      label: "Супровый конверт",
      representation: { geometry: "Supra", model: "invariant-envelope" },
      invariant: {
        constructId: "TZAR-DECLARATION-001",
        author: "Александр Лацинник",
        axisTerm: "осевание",
        axisDefinition: "Осевание — приведение субъектной структуры в состояние, при котором супра становится сущей.",
        version: "1.0.0",
        status: "canonical"
      }
    }
  ],
  negativeControls: [
    {
      label: "Подмена определения",
      representation: { geometry: "Projective", model: "mutated-graph" },
      invariant: {
        constructId: "TZAR-DECLARATION-001",
        author: "Александр Лацинник",
        axisTerm: "осевание",
        axisDefinition: "Осевание — приведение субъектной структуры в состояние, при котором супра становится наблюдаемой.",
        version: "1.0.0",
        status: "canonical"
      }
    }
  ]
};
