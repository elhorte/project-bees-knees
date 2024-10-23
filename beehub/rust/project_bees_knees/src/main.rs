
use ndarray::{Array1, Zip};
use rand;
//use std::f64::consts::PI;
use ndarray::s;

fn main() {
    let sensor1_data = read_sensor_data();
    let sensor2_data = read_sensor_data();

    let sensor1_data_normalized = normalize(&sensor1_data);
    let sensor2_data_normalized = normalize(&sensor2_data);

    let common_signal = cross_correlation(&sensor1_data_normalized, &sensor2_data_normalized);

    // For demonstration, print the first 10 samples of the result
    for value in common_signal.iter().take(10) {
        println!("{}", value);
    }
}

fn read_sensor_data() -> Array1<f64> {
    // Simulate reading sensor data with random values
    Array1::from_iter((0..192000).map(|_| rand::random::<f64>()))
}

fn normalize(data: &Array1<f64>) -> Array1<f64> {
    // Normalize the data by subtracting the mean
    let mean = data.mean().unwrap();
    data - mean
}

/*
fn cross_correlation(signal1: &Array1<f64>, signal2: &Array1<f64>) -> Array1<f64> {
    // Compute the cross-correlation between two signals
    let n = signal1.len();
    let mut result = Array1::<f64>::zeros(n);

    for (shift, value) in result.iter_mut().enumerate() {
        *value = Zip::from(signal1.view())
            .and(signal2.view().slice(s![shift..]))
            .fold(0.0, |acc, &a, &b| acc + a * b);
    }
*/
fn cross_correlation(signal1: &Array1<f64>, signal2: &Array1<f64>) -> Array1<f64> {
    let n = signal1.len();
    let mut result = Array1::<f64>::zeros(n);

    for shift in 0..n {
        // Print heartbeat message every 1000 iterations
        if shift % 1000 == 0 {
            println!("Processing: iteration {}", shift / 1000);
        }

        let end = n - shift;
        let s1_slice = signal1.slice(s![..end]);
        let s2_slice = signal2.slice(s![shift..]);
        let corr_value = Zip::from(&s1_slice)
            .and(&s2_slice)
            .fold(0.0, |acc, &a, &b| acc + a * b);
        result[shift] = corr_value;
    }

    result
}

/*
In Rust, we will use crates such as ndarray for numerical computations and rand for generating random data, as there's no direct equivalent to NumPy in the Rust ecosystem.

The Rust version of the script will:

Generate random data to simulate sensor readings.
Normalize the data by subtracting the mean.
Compute the cross-correlation.
This script includes the following changes and considerations:

We use ndarray for array manipulations, similar to NumPy in Python.
The rand crate generates random data.

The cross-correlation implementation is simplified and may differ from NumPy's correlate in efficiency and exact behavior. The Rust version computes the correlation by shifting the second signal and calculating the dot product for each shift.

Rust requires careful handling of array slices and bounds, which can make the cross-correlation code more verbose compared to Python.
Please note that this Rust code assumes a basic level of familiarity with Rust syntax and may require adjustments based on your specific use case and Rust environment.
*/
