import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"

const GithubSponsor: QuartzComponent = ({ displayClass }: QuartzComponentProps) => {
  return (
    <div class={`github-sponsor ${displayClass ?? ""}`}>
      <iframe
        src="https://github.com/sponsors/arturgoms/button"
        title="Sponsor arturgoms"
        height="32"
        width="114"
        style="border: 0; border-radius: 6px;"
      />
    </div>
  )
}

GithubSponsor.css = `
.github-sponsor {
  display: flex;
  justify-content: center;
}
`

export default (() => GithubSponsor) satisfies QuartzComponentConstructor
