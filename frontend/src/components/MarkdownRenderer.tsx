import { memo, useCallback, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { theme } from 'antd';
import type { Components } from 'react-markdown';
import type React from 'react';
import type { CSSProperties } from 'react';

// react-syntax-highlighter 类型定义与运行时风格对象不匹配，需中间转换
const codeStyle = oneDark as unknown as Record<string, CSSProperties>;

interface MarkdownRendererProps {
  content: string;
}

const CopyButton: React.FC<{ code: string }> = ({ code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      // HTTP 环境下 clipboard API 不可用，降级到 execCommand
      const textarea = document.createElement('textarea');
      textarea.value = code;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
    }
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <button
      onClick={handleCopy}
      style={{
        position: 'absolute',
        top: 8,
        right: 8,
        background: 'rgba(255,255,255,0.1)',
        border: '1px solid rgba(255,255,255,0.2)',
        borderRadius: 4,
        color: '#ccc',
        cursor: 'pointer',
        padding: '2px 8px',
        fontSize: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
      }}
      title="复制代码"
    >
      {copied ? <><CheckOutlined /> 已复制</> : <><CopyOutlined /> 复制</>}
    </button>
  );
};

const components: Components = {
  code({ className, children, ...rest }) {
    const match = /language-(\w+)/.exec(className || '');
    const codeString = String(children).replace(/\n$/, '');
    const isBlock = match || codeString.includes('\n');

    // 多行代码块
    if (isBlock) {
      return (
        <div style={{ position: 'relative' }}>
          {match && (
            <div style={{
              padding: '4px 12px',
              background: '#2d2d2d',
              borderTopLeftRadius: 8,
              borderTopRightRadius: 8,
              color: '#999',
              fontSize: 12,
              fontFamily: 'monospace',
            }}>
              {match[1]}
            </div>
          )}
          <CopyButton code={codeString} />
          <SyntaxHighlighter
            style={codeStyle}
            language={match?.[1] || 'text'}
            PreTag="div"
            customStyle={{
              margin: 0,
              borderTopLeftRadius: match ? 0 : 8,
              borderTopRightRadius: match ? 0 : 8,
              borderBottomLeftRadius: 8,
              borderBottomRightRadius: 8,
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </div>
      );
    }

    // 行内代码
    return (
      <code
        className={className}
        style={{
          background: 'rgba(0,0,0,0.06)',
          padding: '2px 6px',
          borderRadius: 4,
          fontSize: '0.9em',
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
        }}
        {...rest}
      >
        {children}
      </code>
    );
  },
  table({ children, ...rest }) {
    return (
      <div style={{ overflowX: 'auto', margin: '8px 0' }}>
        <table
          style={{
            borderCollapse: 'collapse',
            width: '100%',
            fontSize: 14,
          }}
          {...rest}
        >
          {children}
        </table>
      </div>
    );
  },
};

const MarkdownRenderer: React.FC<MarkdownRendererProps> = memo(({ content }) => {
  const { token } = theme.useToken();

  const mdComponents = useMemo<Components>(() => ({
    ...components,
    th({ children, ...rest }) {
      return (
        <th
          style={{
            border: `1px solid ${token.colorBorderSecondary}`,
            padding: '8px 12px',
            background: token.colorBgLayout,
            fontWeight: 600,
            textAlign: 'left',
          }}
          {...rest}
        >
          {children}
        </th>
      );
    },
    td({ children, ...rest }) {
      return (
        <td
          style={{
            border: `1px solid ${token.colorBorderSecondary}`,
            padding: '8px 12px',
          }}
          {...rest}
        >
          {children}
        </td>
      );
    },
    a({ children, href, ...rest }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: token.colorPrimary }}
          {...rest}
        >
          {children}
        </a>
      );
    },
    blockquote({ children, ...rest }) {
      return (
        <blockquote
          style={{
            borderLeft: `3px solid ${token.colorPrimary}`,
            paddingLeft: 12,
            margin: '8px 0',
            color: token.colorTextSecondary,
          }}
          {...rest}
        >
          {children}
        </blockquote>
      );
    },
  }), [token]);

  return (
    <div className="markdown-body" style={{ lineHeight: 1.7, fontSize: 14 }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
});

MarkdownRenderer.displayName = 'MarkdownRenderer';

export default MarkdownRenderer;
