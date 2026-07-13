import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 20,               // 20 concurrent virtual users
  duration: '30s',       // sustained for 30 seconds
  thresholds: {
    http_req_duration: ['p(95)<800'],   // 95th percentile under 800 ms
    http_req_failed: ['rate<0.02'],     // error rate under 2%
  },
};

export default function () {
  const health = http.get('http://localhost:8000/health');
  check(health, { 'health is 200': (r) => r.status === 200 });

  const email = `perf-${__VU}-${__ITER}@example.com`;
  const payload = JSON.stringify({ email: email, password: 'Password123' });
  const params = { headers: { 'Content-Type': 'application/json' } };

  const register = http.post('http://localhost:8000/api/v1/register', payload, params);
  check(register, { 'register is 201': (r) => r.status === 201 });

  const login = http.post('http://localhost:8000/api/v1/login', payload, params);
  check(login, { 'login is 200': (r) => r.status === 200 });
}