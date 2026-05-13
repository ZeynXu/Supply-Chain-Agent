import { Card, Statistic, Row, Col, DatePicker, Button, Space, Table, Tag, Typography } from 'antd';
import {
  FieldTimeOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  ToolOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { useEffect, useState, useCallback } from 'react';
import { statsService } from '@/api/statsService';
import type { DashboardStats } from '@/types/dashboard';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;
const { Title } = Typography;

export const DashboardPage = () => {
  const [stats, setStats] = useState<DashboardStats>({
    totalWorkorders: 0,
    avgProcessingTime: 0,
    automationRate: 0,
    toolSuccessRate: 0,
  });
  const [trendData, setTrendData] = useState<{ date: string; count: number }[]>([]);
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs]>([
    dayjs().subtract(7, 'day'),
    dayjs(),
  ]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const statsData = await statsService.getDashboardStats();
      setStats(statsData);
      const trend = await statsService.getTrendData(7);
      setTrendData(trend);
    } catch (error) {
      console.error('获取数据失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    // 30秒自动轮询
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // 趋势图配置
  const trendOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      borderColor: 'transparent',
      textStyle: { color: '#fff' },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: trendData.map((d) => d.date),
      boundaryGap: false,
      axisLine: { lineStyle: { color: 'var(--border-color)' } },
      axisLabel: { color: 'var(--text-secondary)' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: 'var(--border-light)' } },
      axisLabel: { color: 'var(--text-secondary)' },
    },
    series: [
      {
        name: '工单数量',
        type: 'line',
        data: trendData.map((d) => d.count),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: {
          width: 3,
          color: '#2A5C82',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(42, 92, 130, 0.3)' },
              { offset: 1, color: 'rgba(42, 92, 130, 0.02)' },
            ],
          },
        },
        itemStyle: { color: '#2A5C82' },
      },
    ],
  };

  // 分布图配置
  const distributionOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      bottom: '5%',
      left: 'center',
      textStyle: { color: 'var(--text-secondary)' },
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: 'var(--bg-primary)',
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 14,
            fontWeight: 'bold',
          },
        },
        labelLine: {
          show: false,
        },
        data: [
          { value: 35, name: '状态查询', itemStyle: { color: '#1890ff' } },
          { value: 30, name: '工单创建', itemStyle: { color: '#52c41a' } },
          { value: 20, name: '异常上报', itemStyle: { color: '#faad14' } },
          { value: 15, name: '审批流转', itemStyle: { color: '#722ed1' } },
        ],
      },
    ],
  };

  // 工单队列数据
  const queueData = [
    { id: 'WO-001', summary: '质量检验工单', status: 'completed', processingTime: 2.5, createdAt: '2026-04-30T10:00:00' },
    { id: 'WO-002', summary: '物流异常工单', status: 'processing', processingTime: 1.2, createdAt: '2026-04-30T10:15:00' },
    { id: 'WO-003', summary: '合同审核工单', status: 'pending', processingTime: 0, createdAt: '2026-04-30T10:30:00' },
    { id: 'WO-004', summary: '采购申请工单', status: 'completed', processingTime: 3.8, createdAt: '2026-04-30T09:45:00' },
    { id: 'WO-005', summary: '供应商对账工单', status: 'processing', processingTime: 0.8, createdAt: '2026-04-30T10:20:00' },
  ];

  // 表格列配置
  const columns = [
    {
      title: '工单ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      render: (id: string) => (
        <span style={{ color: 'var(--color-primary)', fontWeight: 500 }}>{id}</span>
      ),
    },
    { title: '描述摘要', dataIndex: 'summary', key: 'summary', ellipsis: true },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config: Record<string, { color: string; text: string }> = {
          completed: { color: 'success', text: '已完成' },
          processing: { color: 'processing', text: '处理中' },
          pending: { color: 'default', text: '待处理' },
          failed: { color: 'error', text: '失败' },
        };
        const { color, text } = config[status] || { color: 'default', text: status };
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '处理时长',
      dataIndex: 'processingTime',
      key: 'processingTime',
      width: 100,
      render: (time: number) => (time > 0 ? `${time}s` : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 150,
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
  ];

  return (
    <div
      style={{
        padding: 24,
        paddingTop: 70,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 'calc(100vh - 70px)',
        boxSizing: 'border-box'
      }}
    >
      {/* 页面标题栏 */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          marginBottom: 24,
          flexShrink: 0,
          gap: 16
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          工单处理统计仪表板
        </Title>
        <Space>
          <RangePicker
            value={dateRange}
            onChange={(dates) => dates && setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs])}
          />
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchData}
            loading={loading}
            style={{ borderRadius: 6 }}
          >
            刷新
          </Button>
        </Space>
      </div>

      {/* 关键指标卡片 - 固定高度区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24, flexShrink: 0 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card" style={{ borderRadius: 12, height: '100%' }}>
            <Statistic
              title="今日工单总数"
              value={stats.totalWorkorders}
              prefix={<FileTextOutlined />}
              loading={loading}
              valueStyle={{ color: 'var(--color-primary)' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card" style={{ borderRadius: 12, height: '100%' }}>
            <Statistic
              title="平均处理时长"
              value={stats.avgProcessingTime.toFixed(2)}
              suffix="秒"
              prefix={<FieldTimeOutlined />}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card" style={{ borderRadius: 12, height: '100%' }}>
            <Statistic
              title="自动化完成率"
              value={stats.automationRate.toFixed(1)}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
              loading={loading}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card className="stat-card" style={{ borderRadius: 12, height: '100%' }}>
            <Statistic
              title="工具调用成功率"
              value={stats.toolSuccessRate.toFixed(1)}
              suffix="%"
              prefix={<ToolOutlined />}
              valueStyle={{ color: '#1890ff' }}
              loading={loading}
            />
          </Card>
        </Col>
      </Row>

      {/* 图表区域 - 可伸缩区域 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24, flex: 1, minHeight: 400 }}>
        <Col xs={24} lg={16}>
          <Card
            title="近7日工单处理量趋势"
            style={{ borderRadius: 12, height: '100%' }}
            styles={{ body: { padding: '16px 16px 4px 16px', height: 'calc(100% - 56px)' } }}
          >
            <ReactECharts
              option={trendOption}
              style={{ height: '100%' }}
              opts={{ renderer: 'svg' }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title="工单类型分布"
            style={{ borderRadius: 12, height: '100%' }}
            styles={{ body: { padding: '16px 16px 4px 16px', height: 'calc(100% - 56px)' } }}
          >
            <ReactECharts
              option={distributionOption}
              style={{ height: '100%' }}
              opts={{ renderer: 'svg' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 实时工单队列 - 可滚动区域 */}
      <Card
        title="实时工单队列"
        style={{
          borderRadius: 12,
          flexShrink: 0,
          maxHeight: '400px',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
        styles={{
          body: {
            flex: 1,
            overflow: 'auto',
            padding: 0
          }
        }}
        extra={
          <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            每30秒自动刷新
          </span>
        }
      >
        <Table
          dataSource={queueData}
          columns={columns}
          size="small"
          pagination={{
            pageSize: 5,
            showSizeChanger: false,
            showTotal: (total, range) => `${range[0]}-${range[1]} 共 ${total} 条`
          }}
          rowKey="id"
          scroll={{ y: 250 }}
          style={{ border: 'none' }}
        />
      </Card>
    </div>
  );
};

export default DashboardPage;
