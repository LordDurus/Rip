// TODO: parallelize axis FFT passes with rayon
use rustfft::{FftPlanner, num_complex::Complex};

/// Solves ∇²φ = 4πGρ using FFT (spectral Poisson solver).
/// Returns (gx, gy, gz) grids — one gravity vector component per cell.
pub fn compute_gravity_fft(density: &Vec<Vec<Vec<f64>>>, gravity_constant: f64, grid_height: usize, grid_width: usize, grid_depth: usize) -> (Vec<Vec<Vec<f64>>>, Vec<Vec<Vec<f64>>>, Vec<Vec<Vec<f64>>>) {
    let n = grid_height * grid_width * grid_depth;

    // Flatten density into 1D complex buffer (row-major)
    let mut buffer: Vec<Complex<f64>> = (0..grid_height).flat_map(|h| (0..grid_width).flat_map(move |w| (0..grid_depth).map(move |d| Complex::new(density[h][w][d], 0.0)))).collect();

    // Forward FFT along each axis (3D FFT via three 1D passes)
    fft_3d_forward(&mut buffer, grid_height, grid_width, grid_depth);

    // Solve Poisson in frequency space: φ_k = -4πG * ρ_k / |k|²
    // Then multiply by ik to get gravity components
    let mut gx_buf = vec![Complex::new(0.0, 0.0); n];
    let mut gy_buf = vec![Complex::new(0.0, 0.0); n];
    let mut gz_buf = vec![Complex::new(0.0, 0.0); n];

    for ih in 0..grid_height {
        for iw in 0..grid_width {
            for id in 0..grid_depth {
                let idx = ih * grid_width * grid_depth + iw * grid_depth + id;

                // Wavenumbers (shifted for negative frequencies)
                let kh = wavenumber(ih, grid_height);
                let kw = wavenumber(iw, grid_width);
                let kd = wavenumber(id, grid_depth);
                let k2 = kh * kh + kw * kw + kd * kd;

                if k2 == 0.0 {
                    // Zero mode — set mean potential to zero (Jeans swindle)
                    continue;
                }

                let phi_k = buffer[idx] * (-4.0 * std::f64::consts::PI * gravity_constant / k2);

                // Gravity = -∇φ → in frequency space: -ik * φ_k
                // Multiplying by -ik: Complex(im * k) * phi_k = phi_k * Complex(0, -k)
                gx_buf[idx] = phi_k * Complex::new(0.0, -kh);
                gy_buf[idx] = phi_k * Complex::new(0.0, -kw);
                gz_buf[idx] = phi_k * Complex::new(0.0, -kd);
            }
        }
    }

    // Inverse FFT to get real-space gravity
    fft_3d_inverse(&mut gx_buf, grid_height, grid_width, grid_depth);
    fft_3d_inverse(&mut gy_buf, grid_height, grid_width, grid_depth);
    fft_3d_inverse(&mut gz_buf, grid_height, grid_width, grid_depth);

    let norm = n as f64;

    // Reshape back to 3D grids
    let mut gx = vec![vec![vec![0.0; grid_depth]; grid_width]; grid_height];
    let mut gy = vec![vec![vec![0.0; grid_depth]; grid_width]; grid_height];
    let mut gz = vec![vec![vec![0.0; grid_depth]; grid_width]; grid_height];

    for ih in 0..grid_height {
        for iw in 0..grid_width {
            for id in 0..grid_depth {
                let idx = ih * grid_width * grid_depth + iw * grid_depth + id;
                gx[ih][iw][id] = gx_buf[idx].re / norm;
                gy[ih][iw][id] = gy_buf[idx].re / norm;
                gz[ih][iw][id] = gz_buf[idx].re / norm;
            }
        }
    }

    (gx, gy, gz)
}

/// Wavenumber for index i in a grid of size n (handles negative frequencies)
#[inline(always)]
fn wavenumber(i: usize, n: usize) -> f64 {
    let i = i as f64;
    let n = n as f64;
    if i <= n / 2.0 { i } else { i - n }
}

fn fft_3d_forward(buf: &mut Vec<Complex<f64>>, nh: usize, nw: usize, nd: usize) {
    let mut planner = FftPlanner::new();
    fft_axis(buf, nh, nw, nd, 0, &mut planner, false);
    fft_axis(buf, nh, nw, nd, 1, &mut planner, false);
    fft_axis(buf, nh, nw, nd, 2, &mut planner, false);
}

fn fft_3d_inverse(buf: &mut Vec<Complex<f64>>, nh: usize, nw: usize, nd: usize) {
    let mut planner = FftPlanner::new();
    fft_axis(buf, nh, nw, nd, 0, &mut planner, true);
    fft_axis(buf, nh, nw, nd, 1, &mut planner, true);
    fft_axis(buf, nh, nw, nd, 2, &mut planner, true);
}

/// Run FFT along one axis of the 3D buffer
fn fft_axis(buf: &mut Vec<Complex<f64>>, nh: usize, nw: usize, nd: usize, axis: usize, planner: &mut FftPlanner<f64>, inverse: bool) {
    let n_axis = match axis {
        0 => nh,
        1 => nw,
        2 => nd,
        _ => unreachable!(),
    };
    let fft = if inverse { planner.plan_fft_inverse(n_axis) } else { planner.plan_fft_forward(n_axis) };

    // let scratch = vec![Complex::new(0.0, 0.0); fft.get_outofplace_scratch_len()];

    // Extract each line along this axis, FFT it, write back
    match axis {
        0 => {
            for iw in 0..nw {
                for id in 0..nd {
                    let mut line: Vec<Complex<f64>> = (0..nh).map(|ih| buf[ih * nw * nd + iw * nd + id]).collect();
                    fft.process(&mut line);
                    for ih in 0..nh {
                        buf[ih * nw * nd + iw * nd + id] = line[ih];
                    }
                }
            }
        }
        1 => {
            for ih in 0..nh {
                for id in 0..nd {
                    let mut line: Vec<Complex<f64>> = (0..nw).map(|iw| buf[ih * nw * nd + iw * nd + id]).collect();
                    fft.process(&mut line);
                    for iw in 0..nw {
                        buf[ih * nw * nd + iw * nd + id] = line[iw];
                    }
                }
            }
        }
        2 => {
            for ih in 0..nh {
                for iw in 0..nw {
                    let mut line: Vec<Complex<f64>> = (0..nd).map(|id| buf[ih * nw * nd + iw * nd + id]).collect();
                    fft.process(&mut line);
                    for id in 0..nd {
                        buf[ih * nw * nd + iw * nd + id] = line[id];
                    }
                }
            }
        }
        _ => unreachable!(),
    }
}
