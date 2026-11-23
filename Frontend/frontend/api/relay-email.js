import nodemailer from 'nodemailer'

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization')

  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { host, port, user, password, sender, emails } = req.body || {}
  const emailList = Array.isArray(emails) ? emails : [req.body || {}]

  const smtpUser = user || 'dyfs2m763cn7s2uz@ethereal.email'
  const smtpPass = password || 'KFHKGSc119pe56eY4f'
  const smtpHost = host || 'smtp.ethereal.email'
  const smtpPort = Number(port) || 587

  try {
    const transporter = nodemailer.createTransport({
      host: smtpHost,
      port: smtpPort,
      secure: smtpPort === 465,
      auth: {
        user: smtpUser,
        pass: smtpPass,
      },
    })

    // Parallel dispatch with Promise.allSettled for high throughput
    const promises = emailList.map(async (item) => {
      const recipient = item.recipient || item.recipient_email
      const subject = item.subject
      const text = item.body || item.body_text || ''
      const html = item.html_body || undefined
      const from = item.sender || sender || `Manufacturing 360 <${smtpUser}>`

      if (!recipient || !subject) {
        return { recipient, success: false, error: 'Missing recipient or subject' }
      }

      try {
        const info = await transporter.sendMail({
          from,
          to: recipient,
          subject,
          text,
          html,
        })
        return { recipient, success: true, messageId: info.messageId }
      } catch (sendErr) {
        return { recipient, success: false, error: sendErr.message }
      }
    })

    const settled = await Promise.allSettled(promises)
    const results = settled.map((s, idx) => {
      if (s.status === 'fulfilled') return s.value
      const rec = emailList[idx]?.recipient || emailList[idx]?.recipient_email
      return { recipient: rec, success: false, error: s.reason?.message || 'Unknown send error' }
    })

    const successCount = results.filter((r) => r.success).length
    return res.status(200).json({ success: true, count: results.length, successCount, results })
  } catch (err) {
    return res.status(500).json({ success: false, error: err.message })
  }
}
