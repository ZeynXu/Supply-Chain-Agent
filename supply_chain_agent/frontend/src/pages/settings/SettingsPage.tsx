import { Card, Form, Input, Select, Button, Space, Alert, Switch, Divider, Typography } from 'antd';
import {
  SaveOutlined,
  GlobalOutlined,
  ApiOutlined,
  ExperimentOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { useUIStore } from '@/store/uiStore';
import { useConversationStore } from '@/store/conversationStore';
import { useEffect, useState, useCallback } from 'react';

const { Title, Text } = Typography;

const models = [
  { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet-20241022' },
  { label: 'Claude 3 Opus', value: 'claude-3-opus-20240229' },
  { label: 'Claude 3 Sonnet', value: 'claude-3-sonnet-20240229' },
  { label: 'GPT-4', value: 'gpt-4' },
  { label: 'GPT-4 Turbo', value: 'gpt-4-turbo' },
];

export const SettingsPage = () => {
  const { apiUrl, wsUrl, modelName, setApiUrl, setWsUrl, setModelName } = useUIStore();
  const { useMock, setUseMock } = useConversationStore();
  const [form] = Form.useForm();
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    form.setFieldsValue({ apiUrl, wsUrl, modelName, useMock });
  }, [apiUrl, wsUrl, modelName, useMock, form]);

  const handleSave = useCallback(
    (values: { apiUrl: string; wsUrl: string; modelName: string; useMock: boolean }) => {
      setApiUrl(values.apiUrl);
      setWsUrl(values.wsUrl);
      setModelName(values.modelName);
      setUseMock(values.useMock);
      localStorage.setItem('sca-settings', JSON.stringify(values));
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
    [setApiUrl, setWsUrl, setModelName, setUseMock]
  );

  const handleReset = useCallback(() => {
    form.setFieldsValue({
      apiUrl: '/api',
      wsUrl: 'ws://localhost:8000',
      modelName: 'claude-3-5-sonnet-20241022',
      useMock: true,
    });
  }, [form]);

  return (
    <div style={{ padding: 24, paddingTop: 70, maxWidth: 800, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        系统设置
      </Title>

      {saved && (
        <Alert
          message="设置已保存"
          type="success"
          showIcon
          closable
          style={{ marginBottom: 24, borderRadius: 8 }}
        />
      )}

      {/* 连接配置 */}
      <Card
        title={
          <Space>
            <ApiOutlined />
            <span>连接配置</span>
          </Space>
        }
        style={{ marginBottom: 24, borderRadius: 12 }}
      >
        <Form form={form} layout="vertical" onFinish={handleSave} requiredMark="optional">
          <Form.Item
            name="apiUrl"
            label={
              <Space>
                <ApiOutlined />
                <span>API 地址</span>
              </Space>
            }
            rules={[{ required: true, message: '请输入 API 地址' }]}
            tooltip="后端 API 服务地址"
          >
            <Input placeholder="http://localhost:8000/api" style={{ borderRadius: 6 }} />
          </Form.Item>

          <Form.Item
            name="wsUrl"
            label={
              <Space>
                <GlobalOutlined />
                <span>WebSocket 地址</span>
              </Space>
            }
            rules={[{ required: true, message: '请输入 WebSocket 地址' }]}
            tooltip="WebSocket 连接地址，用于实时通信"
          >
            <Input placeholder="ws://localhost:8000/ws" style={{ borderRadius: 6 }} />
          </Form.Item>

          <Form.Item
            name="modelName"
            label={
              <Space>
                <ExperimentOutlined />
                <span>模型选择</span>
              </Space>
            }
            rules={[{ required: true, message: '请选择模型' }]}
            tooltip="后端使用的 AI 模型"
          >
            <Select options={models} style={{ borderRadius: 6 }} />
          </Form.Item>

          <Divider />

          <Form.Item
            name="useMock"
            label="使用 Mock 模式"
            valuePropName="checked"
            tooltip="开启后将使用模拟数据，无需后端服务"
          >
            <Switch checkedChildren="Mock" unCheckedChildren="真实API" style={{ borderRadius: 4 }} />
          </Form.Item>

          <Alert
            message={
              <Space>
                <InfoCircleOutlined />
                <span>
                  {useMock
                    ? '当前使用 Mock 模式，将返回模拟数据'
                    : '当前使用真实 API，请确保后端服务已启动'}
                </span>
              </Space>
            }
            type={useMock ? 'info' : 'warning'}
            showIcon={false}
            style={{ marginBottom: 16, borderRadius: 8 }}
          />

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                size="large"
                style={{ borderRadius: 8 }}
              >
                保存设置
              </Button>
              <Button size="large" onClick={handleReset} style={{ borderRadius: 8 }}>
                重置默认
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      {/* 关于 */}
      <Card
        title={
          <Space>
            <InfoCircleOutlined />
            <span>关于系统</span>
          </Space>
        }
        style={{ borderRadius: 12 }}
      >
        <div style={{ textAlign: 'center', padding: '12px 0' }}>
          <Title level={4} style={{ color: 'var(--color-primary)', margin: '0 0 8px 0' }}>
            智能供应链 Agent 系统
          </Title>
          <Text type="secondary">版本: 1.0.0</Text>
          <br />
          <Text type="secondary">基于 React 18 + TypeScript + Ant Design 5 构建</Text>
          <br />
          <Text type="secondary">Multi-Agent 协作平台，自动处理供应链工单</Text>
        </div>
      </Card>
    </div>
  );
};

export default SettingsPage;
