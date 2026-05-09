import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import { useCallback } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  text: string
  className?: string
}

const SHELL_LANGS = new Set(['bash', 'sh', 'shell'])

function CodeBlock({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLElement>) {
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
          <button
            onClick={copy}
            className="copy-btn text-xs text-stone-400 hover:text-stone-700 dark:hover:text-stone-200"
            aria-label="Copy code"
          >
            Copy
          </button>
        </div>
      )}
      {!isShell && (
        <button
          onClick={copy}
          className="copy-btn absolute right-2 top-2 hidden text-xs text-stone-400 hover:text-stone-700 group-hover:block dark:hover:text-stone-200"
          aria-label="Copy code"
        >
          Copy
        </button>
      )}
      <code className={cn(className, 'block overflow-x-auto p-4 text-sm')} {...props}>
        {children}
      </code>
    </div>
  )
}

export function Answer({ text, className }: Props) {
  return (
    <div className={cn('prose prose-stone dark:prose-invert max-w-none text-sm leading-relaxed', className)}>
      <ReactMarkdown
        rehypePlugins={[rehypeHighlight]}
        components={{
          code: CodeBlock as never,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
