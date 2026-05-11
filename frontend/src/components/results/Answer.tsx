import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'
import { useCallback } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  text: string
  className?: string
}

const SHELL_LANGS = new Set(['bash', 'sh', 'shell'])

function CodeBlock({ className, children }: React.HTMLAttributes<HTMLElement>) {
  const lang = /language-(\w+)/.exec(className ?? '')?.[1] ?? ''
  const isShell = SHELL_LANGS.has(lang)
  const code = String(children).replace(/\n$/, '')

  const copy = useCallback(() => {
    navigator.clipboard.writeText(code)
  }, [code])

  return (
    <div className="code-block-wrapper group relative my-3 overflow-hidden rounded-lg border border-stone-200 dark:border-stone-700">
      {isShell && (
        <div className="flex items-center justify-between border-b border-stone-200 bg-stone-100 px-3 py-1.5 dark:border-stone-700 dark:bg-stone-800">
          <span className="text-xs font-medium text-stone-500">bash</span>
          <button onClick={copy} className="copy-btn text-xs text-stone-400 hover:text-stone-700 dark:hover:text-stone-200" aria-label="Copy code">
            Copy
          </button>
        </div>
      )}
      {!isShell && (
        <button onClick={copy} className="copy-btn absolute right-2 top-2 hidden text-xs text-stone-400 hover:text-stone-700 group-hover:block dark:hover:text-stone-200" aria-label="Copy code">
          Copy
        </button>
      )}
      <code className={cn(className, 'block overflow-x-auto p-4 text-sm')}>
        {children}
      </code>
    </div>
  )
}

// Inline code — single backticks inside prose text
function InlineCode({ children }: React.HTMLAttributes<HTMLElement>) {
  return (
    <code className="rounded bg-stone-100 px-1 py-0.5 text-[0.85em] font-mono text-stone-700 dark:bg-stone-800 dark:text-stone-300">
      {children}
    </code>
  )
}

export function Answer({ text, className }: Props) {
  return (
    <div className={cn('prose prose-stone dark:prose-invert max-w-none text-sm leading-relaxed', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          // pre wraps fenced code blocks — delegate to CodeBlock
          pre: ({ children }) => <>{children}</>,
          code: (({ className: cls, children, node, ...props }) => {
            // If parent is <pre>, it's a fenced block; otherwise inline
            const isBlock = node?.position && String(children).includes('\n')
            if (isBlock) return <CodeBlock className={cls} {...props}>{children}</CodeBlock>
            return <InlineCode className={cls} {...props}>{children}</InlineCode>
          }) as never,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
