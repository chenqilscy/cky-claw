/**
 * ConditionRuleEditor — 条件启用规则结构化编辑器。
 *
 * 将自由 JSON conditions 替换为可视化规则编辑器：
 * - match: all (AND) / any (OR)
 * - rules[]: field + operator + value
 * - 支持的字段来自 RunContext metadata
 */
import { useState, useEffect, useCallback } from 'react';
import { Button, Select, Input, Space, Typography, Segmented, App, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined, CodeOutlined, FormOutlined } from '@ant-design/icons';
import { JsonEditor } from './index';

const { Text } = Typography;

/* ---- 可用字段 ---- */
const CONDITION_FIELDS = [
  { label: '环境', value: 'env', placeholder: 'production' },
  { label: '用户 ID', value: 'user_id', placeholder: 'user-xxx' },
  { label: '组织 ID', value: 'org_id', placeholder: 'org-xxx' },
  { label: 'Agent 名称', value: 'agent_name', placeholder: 'my-agent' },
  { label: '对话轮次', value: 'turn_count', placeholder: '5' },
];

/* ---- 运算符 ---- */
const OPERATORS = [
  { label: '等于', value: 'equals' },
  { label: '不等于', value: 'not_equals' },
  { label: '包含于', value: 'in' },
  { label: '不包含于', value: 'not_in' },
  { label: '大于', value: 'gt' },
  { label: '小于', value: 'lt' },
  { label: '≥', value: 'gte' },
  { label: '≤', value: 'lte' },
];

/* ---- 规则类型 ---- */
interface ConditionRule {
  key: string;
  field: string;
  operator: string;
  value: string;
}

interface ConditionConfig {
  match?: 'all' | 'any';
  rules?: Array<{ field: string; operator: string; value: unknown }>;
}

/* ---- 将结构化规则转为存储格式 ---- */
function rulesToConditions(match: 'all' | 'any', rules: ConditionRule[]): Record<string, unknown> {
  if (rules.length === 0) return {};
  return {
    match,
    rules: rules.map((r) => {
      let parsedValue: unknown = r.value;
      /* in / not_in 的 value 作为逗号分隔数组 */
      if (r.operator === 'in' || r.operator === 'not_in') {
        parsedValue = r.value.split(',').map((s) => s.trim()).filter(Boolean);
      } else if (r.field === 'turn_count' && /^\d+$/.test(r.value)) {
        parsedValue = Number(r.value);
      }
      return { field: r.field, operator: r.operator, value: parsedValue };
    }),
  };
}

/* ---- 从存储格式解析为可编辑规则 ---- */
function conditionsToRules(conditions: Record<string, unknown>): { match: 'all' | 'any'; rules: ConditionRule[] } {
  const config = conditions as ConditionConfig;
  const match = config.match ?? 'all';
  const rawRules = config.rules ?? [];
  const rules: ConditionRule[] = rawRules.map((r, i) => ({
    key: `rule_${i}_${Date.now()}`,
    field: r.field,
    operator: r.operator,
    value: Array.isArray(r.value) ? (r.value as string[]).join(', ') : String(r.value ?? ''),
  }));
  return { match: match as 'all' | 'any', rules };
}

/* ========================== 组件 ========================== */

export interface ConditionRuleEditorProps {
  /** 受控值：条件配置对象 */
  value?: Record<string, unknown>;
  /** 值变化回调 */
  onChange?: (conditions: Record<string, unknown>) => void;
  /** 只读 */
  readOnly?: boolean;
}

export default function ConditionRuleEditor({ value = {}, onChange, readOnly }: ConditionRuleEditorProps) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<'visual' | 'json'>('visual');
  const [match, setMatch] = useState<'all' | 'any'>('all');
  const [rules, setRules] = useState<ConditionRule[]>([]);
  const [jsonText, setJsonText] = useState('');

  /* 从 value 初始化 */
  useEffect(() => {
    if (Object.keys(value).length > 0) {
      const parsed = conditionsToRules(value);
      setMatch(parsed.match);
      setRules(parsed.rules);
    } else {
      setMatch('all');
      setRules([]);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /* 规则变化时通知外层 */
  const fireChange = useCallback((m: 'all' | 'any', rs: ConditionRule[]) => {
    onChange?.(rulesToConditions(m, rs));
  }, [onChange]);

  const handleMatchChange = (v: 'all' | 'any') => {
    setMatch(v);
    fireChange(v, rules);
  };

  const handleAddRule = () => {
    const key = `rule_${Date.now()}`;
    const newRules = [...rules, { key, field: 'env', operator: 'equals', value: '' }];
    setRules(newRules);
    fireChange(match, newRules);
  };

  const handleRemoveRule = (key: string) => {
    const newRules = rules.filter((r) => r.key !== key);
    setRules(newRules);
    fireChange(match, newRules);
  };

  const handleRuleChange = (key: string, field: keyof ConditionRule, val: string) => {
    const newRules = rules.map((r) => (r.key === key ? { ...r, [field]: val } : r));
    setRules(newRules);
    fireChange(match, newRules);
  };

  const handleModeChange = (newMode: string | number) => {
    if (newMode === 'json') {
      setJsonText(JSON.stringify(value, null, 2));
    } else if (newMode === 'visual') {
      try {
        const parsed = JSON.parse(jsonText || '{}') as Record<string, unknown>;
        onChange?.(parsed);
        const { match: m, rules: rs } = conditionsToRules(parsed);
        setMatch(m);
        setRules(rs);
      } catch {
        message.warning('JSON 格式无效，已恢复');
      }
    }
    setMode(newMode as 'visual' | 'json');
  };

  const handleJsonBlur = () => {
    try {
      const parsed = JSON.parse(jsonText || '{}') as Record<string, unknown>;
      onChange?.(parsed);
    } catch {
      /* 用户还在编辑 */
    }
  };

  const fieldPlaceholder = (field: string) =>
    CONDITION_FIELDS.find((f) => f.value === field)?.placeholder ?? '';

  return (
    <div>
      {/* ---- 工具栏 ---- */}
      <Space style={{ marginBottom: 8, width: '100%', justifyContent: 'space-between' }} align="center">
        <Text type="secondary" style={{ fontSize: 12 }}>留空表示始终启用</Text>
        <Segmented
          size="small"
          options={[
            { label: <><FormOutlined /> 可视化</>, value: 'visual' },
            { label: <><CodeOutlined /> JSON</>, value: 'json' },
          ]}
          value={mode}
          onChange={handleModeChange}
        />
      </Space>

      {/* ---- JSON 模式 ---- */}
      {mode === 'json' && (
        <div onBlur={handleJsonBlur}>
          <JsonEditor
            height={120}
            value={jsonText}
            onChange={setJsonText}
            readOnly={readOnly}
            placeholder='{"match": "all", "rules": [{"field": "env", "operator": "equals", "value": "production"}]}'
          />
        </div>
      )}

      {/* ---- 可视化模式 ---- */}
      {mode === 'visual' && (
        <div>
          {rules.length > 0 && (
            <Space style={{ marginBottom: 8 }} align="center">
              <Text style={{ fontSize: 12 }}>匹配模式：</Text>
              <Select
                size="small"
                value={match}
                onChange={handleMatchChange}
                style={{ width: 110 }}
                disabled={readOnly}
                options={[
                  { label: '全部满足 (AND)', value: 'all' },
                  { label: '任一满足 (OR)', value: 'any' },
                ]}
              />
            </Space>
          )}

          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {rules.map((rule) => (
              <Space key={rule.key} size={6} align="center" style={{ width: '100%' }} wrap>
                <Select
                  size="small"
                  value={rule.field}
                  style={{ width: 110 }}
                  options={CONDITION_FIELDS}
                  onChange={(v) => handleRuleChange(rule.key, 'field', v)}
                  disabled={readOnly}
                />
                <Select
                  size="small"
                  value={rule.operator}
                  style={{ width: 100 }}
                  options={OPERATORS}
                  onChange={(v) => handleRuleChange(rule.key, 'operator', v)}
                  disabled={readOnly}
                />
                <Input
                  size="small"
                  style={{ width: 180 }}
                  value={rule.value}
                  placeholder={
                    rule.operator === 'in' || rule.operator === 'not_in'
                      ? '逗号分隔多个值'
                      : fieldPlaceholder(rule.field)
                  }
                  onChange={(e) => handleRuleChange(rule.key, 'value', e.target.value)}
                  disabled={readOnly}
                />
                {!readOnly && (
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveRule(rule.key)}
                  />
                )}
              </Space>
            ))}
          </Space>

          {rules.length === 0 && (
            <Empty
              description="无条件规则（始终启用）"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              style={{ padding: '12px 0' }}
            />
          )}

          {!readOnly && (
            <Button
              type="dashed"
              size="small"
              icon={<PlusOutlined />}
              onClick={handleAddRule}
              style={{ marginTop: 8 }}
            >
              添加规则
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
