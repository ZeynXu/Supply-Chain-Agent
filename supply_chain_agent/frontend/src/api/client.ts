import axios from 'axios';

const getBaseUrl = () => {
  // 优先使用 localStorage 中存储的配置
  const storedConfig = localStorage.getItem('sca-settings');
  if (storedConfig) {
    try {
      const config = JSON.parse(storedConfig);
      if (config.apiUrl) return config.apiUrl;
    } catch {
      // 忽略解析错误
    }
  }
  // 默认使用相对路径，由 Vite 代理
  return import.meta.env.VITE_API_BASE_URL || '';
};

const apiClient = axios.create({
  baseURL: getBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 在控制台打印请求接口地址
    const fullUrl = `${config.baseURL}${config.url}`;
    console.log(`[API请求] ${config.method?.toUpperCase()} ${fullUrl}`);

    // 添加认证 token（如果有）
    const token = localStorage.getItem('sca-token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 直接返回 data
apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // 不在拦截器中显示错误消息，让调用方处理
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export default apiClient;
