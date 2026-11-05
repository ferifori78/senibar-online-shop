import client from './client'

// No skipAuth: the catalog is public, but a signed-in roaster should still send
// their token so drafts and full batch records come back.
export const catalogApi = {
  list: (params) => client.get('/products/', { params }),
  detail: (slug) => client.get(`/products/${slug}/`),
  batches: (slug) => client.get(`/products/${slug}/batches/`),
  facets: () => client.get('/products/facets/'),
  // The taste questionnaire. Its wording lives on the server so a change of
  // question does not need a frontend deploy.
  quiz: () => client.get('/products/quiz/'),
  recommend: (answers) => client.post('/products/recommend/', { answers }),
}

export default catalogApi
