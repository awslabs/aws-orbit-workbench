import os

import ray
from ray import tune

HEAD_SERVICE_IP_ENV = "RAY_HEAD_SERVICE_HOST"
HEAD_SERVICE_CLIENT_PORT_ENV = "RAY_HEAD_SERVICE_PORT_CLIENT"


def objective(step, alpha, beta):
    return (0.1 + alpha * step / 100) ** (-1) + beta * 0.1


def training_function(config):
    # Hyperparameters
    alpha, beta = config["alpha"], config["beta"]
    for step in range(10):
        # Iterative training function - can be any arbitrary training procedure.
        intermediate_score = objective(step, alpha, beta)
        # Feed the score back back to Tune.
        tune.report(mean_loss=intermediate_score)


if __name__ == "__main__":
    head_service_ip = os.environ[HEAD_SERVICE_IP_ENV]
    client_port = os.environ[HEAD_SERVICE_CLIENT_PORT_ENV]
    ray.util.connect(f"{head_service_ip}:{client_port}")

    analysis = tune.run(
        training_function,
        config={
            "alpha": tune.grid_search([0.001, 0.01, 0.1]),
            "beta": tune.choice([1, 2, 3])
        })

    print("Best config: ", analysis.get_best_config(
        metric="mean_loss", mode="min"))

    # Get a dataframe for analyzing trial results.
    print('arbitrary')
    df = analysis.results_df
