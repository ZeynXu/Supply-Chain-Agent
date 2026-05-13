import { Card, Table, Button, Modal, Form, Input, Space, Tag, Typography, Alert, Divider } from 'antd';
import {
  PlayCircleOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import { useToolStore } from '@/store/toolStore';
import { toolService } from '@/api/toolService';
import type { Tool, ToolTestResponse, ToolParameter } from '@/types/tool';

const { Text, Title } = Typography;

export const ToolsPage = () => {
  const { tools, toolMetrics, loading, fetchTools, fetchToolMetrics } = useToolStore();
  const [selectedTool, setSelectedTool] = useState<Tool | null>(null);
  const [testModalVisible, setTestModalVisible] = useState(false);
  const [testForm] = Form.useForm();
  const [testResult, setTestResult] = useState<ToolTestResponse | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    fetchTools();
    fetchToolMetrics();
  }, [fetchTools, fetchToolMetrics]);

  const handleTest = useCallback((tool: Tool) => {
    setSelectedTool(tool);
    testForm.resetFields();
    setTestResult(null);
    setTestModalVisible(true);
  }, [testForm]);

  const handleTestSubmit = useCallback(async (values: Record<string, unknown>) => {
    if (!selectedTool) return;
    setTesting(true);
    try {
      const result = await toolService.testTool(selectedTool.name, values);
      setTestResult(result);
    } catch (error) {
      setTestResult({
        tool: selectedTool.name,
        success: false,
        error: error instanceof Error ? error.message : '测试失败',
        responseTime: 0,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setTesting(false);
    }
  }, [selectedTool]);

  // 渲染动态参数表单
  const renderParameterFields = (parameters: ToolParameter[]) => {
    return parameters.map((param) => (
      <Form.Item
        key={param.name}
        name={param.name}
        label={
          <Space>
            <span>{param.name}</span>
            {param.required && <Tag color="red">必填</Tag>}
          </Space>
        }
        rules={[{ required: param.required, message: `请输入 ${param.name}` }]}
        tooltip={param.description}
      >
        {param.type === 'boolean' ? (
          <Input placeholder={param.description} />
        ) : param.type === 'number' ? (
          <Input type="number" placeholder={param.description} />
        ) : param.enum ? (
          <Input placeholder={`可选值: ${param.enum.join(', ')}`} />
        ) : (
          <Input.TextArea placeholder={param.description} autoSize={{ minRows: 1, maxRows: 4 }} />
        )}
      </Form.Item>
    ));
  };

  // 表格列配置
  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record: Tool) => (
        <Space>
          <ToolOutlined style={{ color: 'var(--color-primary)' }} />
          <span style={{ fontWeight: 500 }}>{name}</span>
          {record.requiresConfirmation && <Tag color="warning">需确认</Tag>}
        </Space>
      ),
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config: Record<string, { color: string; text: string }> = {
          available: { color: 'success', text: '可用' },
          unavailable: { color: 'error', text: '不可用' },
          deprecated: { color: 'warning', text: '已弃用' },
        };
        const { color, text } = config[status] || { color: 'default', text: status };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '调用次数',
      dataIndex: 'callCount',
      key: 'callCount',
      width: 100,
      render: (count: number) => count || 0,
    },
    {
      title: '健康度',
      key: 'health',
      width: 150,
      render: (_: unknown, record: Tool) => {
        const metric = toolMetrics.find((m) => m.name === record.name);
        if (!metric) return '-';
        return (
          <div style={{ fontSize: 12 }}>
            <div>
              成率:{' '}
              <span style={{ color: metric.successRate > 0.9 ? '#52c41a' : '#faad14' }}>
                {(metric.successRate * 100).toFixed(1)}%
              </span>
            </div>
            <div>
              耗时:{' '}
              <span style={{ color: metric.avgTime < 1 ? '#52c41a' : '#faad14' }}>
                {metric.avgTime.toFixed(2)}s
              </span>
            </div>
          </div>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, record: Tool) => (
        <Button
          type="primary"
          size="small"
          icon={<PlayCircleOutlined />}
          onClick={() => handleTest(record)}
          disabled={record.status !== 'available'}
          style={{ borderRadius: 4 }}
        >
          测试
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, paddingTop: 70 }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        工具管理与监控
      </Title>

      <Card
        title={
          <Space>
            <ToolOutlined />
            <span>可用工具列表</span>
          </Space>
        }
        loading={loading}
        style={{ borderRadius: 12 }}
      >
        <Table
          dataSource={tools}
          columns={columns}
          rowKey="name"
          pagination={{ pageSize: 10, showSizeChanger: true }}
          scroll={{ x: 1000 }}
        />
      </Card>

      {/* 工具测试弹窗 */}
      <Modal
        title={
          <Space>
            <PlayCircleOutlined />
            <span>测试工具: {selectedTool?.name}</span>
          </Space>
        }
        open={testModalVisible}
        onCancel={() => setTestModalVisible(false)}
        footer={null}
        width={700}
      >
        {selectedTool && (
          <div style={{ padding: 16 }}>
            <Alert
              message={selectedTool.description}
              type="info"
              showIcon
              style={{ marginBottom: 16, borderRadius: 8 }}
            />

            <Divider>参数配置</Divider>

            <Form form={testForm} onFinish={handleTestSubmit} layout="vertical">
              {selectedTool.parameters.length > 0 ? (
                renderParameterFields(selectedTool.parameters)
              ) : (
                <Text type="secondary">该工具无需参数</Text>
              )}

              <Form.Item style={{ marginTop: 16, marginBottom: 0 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={testing}
                  block
                  size="large"
                  icon={<PlayCircleOutlined />}
                  style={{ borderRadius: 8 }}
                >
                  执行测试
                </Button>
              </Form.Item>
            </Form>

            {/* 测试结果 */}
            {testResult && (
              <div style={{ marginTop: 24 }}>
                <Divider>测试结果</Divider>
                <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 8 }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: 12,
                    }}
                  >
                    {testResult.success ? (
                      <Space>
                        <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
                        <span style={{ color: '#52c41a', fontWeight: 500 }}>测试成功</span>
                      </Space>
                    ) : (
                      <Space>
                        <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
                        <span style={{ color: '#ff4d4f', fontWeight: 500 }}>测试失败</span>
                      </Space>
                    )}
                    <Space>
                      <HistoryOutlined />
                      <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                        耗时: {(testResult.responseTime * 1000).toFixed(0)}ms
                      </span>
                    </Space>
                  </div>

                  {testResult.success && testResult.response && (
                    <div>
                      <Text strong style={{ marginBottom: 8, display: 'block' }}>
                        返回结果:
                      </Text>
                      <pre
                        style={{
                          background: 'var(--bg-primary)',
                          padding: 12,
                          borderRadius: 6,
                          fontSize: 12,
                          overflow: 'auto',
                          maxHeight: 300,
                          border: '1px solid var(--border-light)',
                        }}
                      >
                        {JSON.stringify(testResult.response, null, 2)}
                      </pre>
                    </div>
                  )}

                  {!testResult.success && testResult.error && (
                    <div>
                      <Text strong style={{ marginBottom: 8, display: 'block', color: '#ff4d4f' }}>
                        错误信息:
                      </Text>
                      <pre
                        style={{
                          background: 'var(--color-error-bg)',
                          padding: 12,
                          borderRadius: 6,
                          color: '#ff4d4f',
                          fontSize: 12,
                          border: '1px solid rgba(255, 77, 79, 0.2)',
                        }}
                      >
                        {testResult.error}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ToolsPage;
