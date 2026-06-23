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
          // Fenced code blocks: <pre><code>…</code></pre>
          // We replace <pre> with a passthrough and detect block code in the
          // code renderer by checking for a language class (always present on
          // fenced blocks) OR actual multi-line content (unnamed fenced blocks).
          pre: ({ children }) => <>{children}</>,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          code: (({ className: cls, children, ...props }: any) => {
            const hasLangClass = !!cls?.startsWith('language-')
            const isMultiline  = String(children).includes('\n')
            const isBlock      = hasLangClass || isMultiline
            if (isBlock) return <CodeBlock className={cls} {...props}>{children}</CodeBlock>
            return <InlineCode {...props}>{children}</InlineCode>
          }),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
